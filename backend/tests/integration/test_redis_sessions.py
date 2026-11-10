import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import timedelta
import json
import os
from types import SimpleNamespace

import pytest
from redis.asyncio.client import Pipeline

from app.application.errors import InvalidGamePhase, PersistenceFailure, SessionUnavailable
from app.application.models import ExpiryPolicy
from app.application.submit_answer import SubmitAnswer
from app.application.session_access import load_authorized
from app.persistence.redis_sessions import RedisSessionRepository, create_redis_client
from app.security.session_tokens import SecureSessionTokens


@pytest.fixture
def redis_url():
    url = os.environ.get('TEST_REDIS_URL')
    if not url:
        pytest.skip('Set TEST_REDIS_URL to run real Redis integration tests')
    return url


@asynccontextmanager
async def environment(url, content):
    client = create_redis_client(url)
    keys = set()

    class TrackedRepository(RedisSessionRepository):
        def key(self, session_id):
            key = super().key(session_id)
            keys.add(key)
            return key

    async def load(question_id, template_id):
        assert question_id == content.question.id and template_id == content.template.id
        return content.question, content.template

    repository = TrackedRepository(client, load)
    tokens = SecureSessionTokens()
    issued = tokens.issue()
    try:
        await client.ping()
        yield SimpleNamespace(client=client, repo=repository, tokens=tokens, issued=issued,
                              key=repository.key(content.active.id))
    finally:
        if keys:
            await client.delete(*keys)
        await client.aclose()


def test_create_get_duplicate_and_no_raw_token(redis_url, game_content):
    async def check():
        async with environment(redis_url, game_content) as env:
            await env.repo.create(game_content.active, token_verifier=env.issued.verifier)
            deadline = await env.client.pexpiretime(env.key)
            stored = await env.repo.get(game_content.active.id)
            assert stored.session == game_content.active
            assert stored.version == 0 and stored.token_verifier == env.issued.verifier
            assert await env.client.pexpiretime(env.key) == deadline
            assert 0 < await env.client.pttl(env.key) <= 900000
            assert env.issued.token.encode() not in await env.client.get(env.key)
            with pytest.raises(PersistenceFailure):
                await env.repo.create(game_content.active, token_verifier=env.issued.verifier)
            assert await env.client.pexpiretime(env.key) == deadline
    asyncio.run(check())


def test_cas_preserves_or_renews_ttl_and_feedback(redis_url, game_content):
    async def check():
        async with environment(redis_url, game_content) as env:
            await env.repo.create(game_content.active, token_verifier=env.issued.verifier)
            await env.client.pexpire(env.key, 60000)
            deadline = await env.client.pexpiretime(env.key)
            assert await env.repo.compare_and_swap(game_content.answered, expected_version=0, expiry=ExpiryPolicy.PRESERVE)
            assert await env.client.pexpiretime(env.key) == deadline
            stored = await env.repo.get(game_content.active.id)
            assert stored.session == game_content.answered and stored.version == 1
            assert not await env.repo.compare_and_swap(game_content.active, expected_version=0, expiry=ExpiryPolicy.RENEW_ACTIVITY)
            assert await env.client.pexpiretime(env.key) == deadline
            assert await env.repo.compare_and_swap(game_content.answered, expected_version=1, expiry=ExpiryPolicy.RENEW_ACTIVITY)
            assert await env.client.pexpiretime(env.key) > deadline + 800000
            assert (await env.repo.get(game_content.active.id)).token_verifier == env.issued.verifier
    asyncio.run(check())


def test_expired_key_cannot_be_resurrected(redis_url, game_content):
    async def check():
        async with environment(redis_url, game_content) as env:
            assert await env.repo.get(game_content.active.id) is None
            await env.repo.create(game_content.active, token_verifier=env.issued.verifier)
            await env.client.pexpireat(env.key, 1)
            assert await env.repo.get(game_content.active.id) is None
            for policy in ExpiryPolicy:
                assert not await env.repo.compare_and_swap(game_content.answered, expected_version=0, expiry=policy)
            assert await env.client.exists(env.key) == 0
    asyncio.run(check())


def test_competing_updates_commit_once(redis_url, game_content, monkeypatch):
    async def check():
        async with environment(redis_url, game_content) as env:
            await env.repo.create(game_content.active, token_verifier=env.issued.verifier)
            original = Pipeline.execute
            barrier = asyncio.Barrier(2)

            async def execute(pipe, *args, **kwargs):
                await barrier.wait()
                return await original(pipe, *args, **kwargs)

            monkeypatch.setattr(Pipeline, 'execute', execute)
            results = await asyncio.wait_for(asyncio.gather(*[
                env.repo.compare_and_swap(game_content.answered, expected_version=0, expiry=ExpiryPolicy.RENEW_ACTIVITY)
                for _ in range(2)
            ]), timeout=5)
            assert sorted(results) == [False, True]
            stored = await env.repo.get(game_content.active.id)
            assert stored.version == 1 and stored.session == game_content.answered
    asyncio.run(check())


def test_expiration_between_watch_and_exec(redis_url, game_content, monkeypatch):
    async def check():
        async with environment(redis_url, game_content) as env:
            await env.repo.create(game_content.active, token_verifier=env.issued.verifier)
            original = Pipeline.execute

            async def execute(pipe, *args, **kwargs):
                await env.client.pexpireat(env.key, 1)
                return await original(pipe, *args, **kwargs)

            monkeypatch.setattr(Pipeline, 'execute', execute)
            assert not await env.repo.compare_and_swap(game_content.answered, expected_version=0, expiry=ExpiryPolicy.RENEW_ACTIVITY)
            assert not await env.client.exists(env.key)
    asyncio.run(check())


def test_invalid_token_and_duplicate_answer(redis_url, game_content):
    async def check():
        async with environment(redis_url, game_content) as env:
            await env.repo.create(game_content.active, token_verifier=env.issued.verifier)
            clock = SimpleNamespace(now=lambda: game_content.now + timedelta(seconds=1))
            submit = SubmitAnswer(env.repo, clock, env.tokens)
            with pytest.raises(SessionUnavailable):
                await submit.execute(game_content.active.id, 'wrong', card_id=game_content.card.id,
                                     answer_option_id=game_content.question.correct_answer_id)
            assert (await env.repo.get(game_content.active.id)).version == 0
            results = await asyncio.gather(*[
                submit.execute(game_content.active.id, env.issued.token, card_id=game_content.card.id,
                               answer_option_id=game_content.question.correct_answer_id) for _ in range(2)
            ], return_exceptions=True)
            assert sum(isinstance(result, InvalidGamePhase) for result in results) == 1
            stored = await load_authorized(env.repo, env.tokens, game_content.active.id, env.issued.token)
            assert stored.version == 1 and stored.session.player.score == 15
    asyncio.run(check())


@pytest.mark.parametrize('version', [-1, True, '0'])
def test_invalid_expected_version(redis_url, game_content, version):
    async def check():
        async with environment(redis_url, game_content) as env:
            with pytest.raises(ValueError):
                await env.repo.compare_and_swap(game_content.active, expected_version=version, expiry=ExpiryPolicy.PRESERVE)
    asyncio.run(check())


@pytest.mark.parametrize('corruption', ['malformed', 'schema', 'version', 'persistent'])
def test_corrupt_storage_fails_explicitly(redis_url, game_content, corruption):
    async def check():
        async with environment(redis_url, game_content) as env:
            await env.repo.create(game_content.active, token_verifier=env.issued.verifier)
            if corruption == 'persistent':
                await env.client.persist(env.key)
            elif corruption == 'malformed':
                await env.client.set(env.key, 'bad', keepttl=True)
            else:
                data = json.loads(await env.client.get(env.key))
                data['schema_version' if corruption == 'schema' else 'version'] = -1
                await env.client.set(env.key, json.dumps(data), keepttl=True)
            with pytest.raises(PersistenceFailure):
                await env.repo.compare_and_swap(game_content.active, expected_version=0, expiry=ExpiryPolicy.PRESERVE)
            if corruption != 'persistent':
                with pytest.raises(PersistenceFailure):
                    await env.repo.get(game_content.active.id)
    asyncio.run(check())


def test_connection_failure_is_not_a_cas_conflict(redis_url, game_content, monkeypatch):
    from redis.exceptions import ConnectionError

    async def check():
        async with environment(redis_url, game_content) as env:
            await env.repo.create(game_content.active, token_verifier=env.issued.verifier)
            attempts = 0

            async def fail(*args, **kwargs):
                nonlocal attempts
                attempts += 1
                raise ConnectionError('Injected connection loss')

            monkeypatch.setattr(Pipeline, '_execute_transaction', fail)
            with pytest.raises(PersistenceFailure, match='Unable to update'):
                await env.repo.compare_and_swap(game_content.answered, expected_version=0, expiry=ExpiryPolicy.RENEW_ACTIVITY)
            assert attempts == 1
            assert (await env.repo.get(game_content.active.id)).version == 0
    asyncio.run(check())


def test_concurrent_next_card_commits_one_draw(redis_url, game_content):
    from random import Random
    from uuid import uuid4
    from app.application.models import GameCatalogs
    from app.application.next_card import NextCard
    from app.domain.card_factory import CardFactory

    async def check():
        async with environment(redis_url, game_content) as env:
            next_question = replace(game_content.question, id=uuid4())
            next_template = replace(game_content.template, positive_effect_budget=0, negative_effect_budget=0)

            async def load_content(qid, tid):
                return (game_content.question if qid == game_content.question.id else next_question,
                        game_content.template if qid == game_content.question.id else next_template)

            async def load_catalog():
                return GameCatalogs((next_question,), (next_template,), ())

            env.repo.load_card_content = load_content
            await env.repo.create(game_content.answered, token_verifier=env.issued.verifier)
            use_case = NextCard(env.repo, SimpleNamespace(load=load_catalog),
                                SimpleNamespace(now=lambda: game_content.now), env.tokens,
                                lambda: CardFactory(Random(42)))
            results = await asyncio.gather(*[
                use_case.execute(game_content.active.id, env.issued.token) for _ in range(2)
            ], return_exceptions=True)
            assert sum(isinstance(result, InvalidGamePhase) for result in results) == 1
            stored = await env.repo.get(game_content.active.id)
            assert stored.version == 1
            assert stored.session.used_question_ids == {game_content.question.id, next_question.id}
            assert stored.session.last_answer_result is None
    asyncio.run(check())


def test_get_state_expiration_preserves_deadline(redis_url, game_content):
    from app.application.get_game_state import GetGameState

    async def check():
        async with environment(redis_url, game_content) as env:
            await env.repo.create(game_content.answered, token_verifier=env.issued.verifier)
            deadline = await env.client.pexpiretime(env.key)
            use_case = GetGameState(env.repo, SimpleNamespace(now=lambda: game_content.now + timedelta(seconds=60)), env.tokens)
            state = await use_case.execute(game_content.active.id, env.issued.token)
            assert state.game_over_reason == 'time_expired'
            assert state.last_answer_result is not None
            assert await env.client.pexpiretime(env.key) == deadline
            assert (await env.repo.get(game_content.active.id)).version == 1
    asyncio.run(check())
