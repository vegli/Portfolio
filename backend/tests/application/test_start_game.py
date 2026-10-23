from dataclasses import FrozenInstanceError, asdict, replace
from datetime import timedelta

import pytest

from app.application.errors import CatalogFailure, NoPlayableQuestions, PersistenceFailure
from .conftest import start


def test_new_and_play_again_are_independent(env):
    first, second = start(env), start(env)
    assert first.state.id != second.state.id
    assert first.token != second.token
    assert first.state.player.hp == 100
    assert first.state.player.score == first.state.player.correct_streak == 0
    assert first.state.remaining_time_ms == 60_000
    assert first.state.phase == 'awaiting_answer'
    assert len(env.factories) == 2
    for game in (first, second):
        stored = env.sessions.records[game.state.id]
        assert stored.session.used_question_ids == {stored.session.current_card.question.id}
        assert game.token not in repr(stored)
        assert game.token not in repr(game)
        assert env.sessions.deadlines[game.state.id] == env.clock.now() + timedelta(minutes=15)
    assert 'correct_answer_id' not in repr(asdict(first.state))
    assert 'token' not in asdict(first.state)


def test_activation_after_catalog_preparation(env):
    env.catalogs.on_load = lambda: env.clock.advance(30)
    game = start(env)
    assert game.state.remaining_time_ms == 60_000
    assert env.sessions.records[game.state.id].session.last_updated_at == env.clock.now()


def test_initial_exhaustion_does_not_store_or_issue_token(env):
    env.catalogs.catalogs = replace(env.catalogs.catalogs, questions=())
    with pytest.raises(NoPlayableQuestions):
        start(env)
    assert not env.sessions.records
    assert env.tokens.count == 0


def test_bad_catalog_is_not_exhaustion(env):
    template = replace(env.catalogs.catalogs.templates[0], positive_effect_budget=1)
    env.catalogs.catalogs = replace(env.catalogs.catalogs, templates=(template,))
    with pytest.raises(CatalogFailure):
        start(env)
    assert not env.sessions.records


def test_safe_projection_contains_no_domain_dataclasses(env):
    state = start(env).state

    def check(value):
        if hasattr(value, '__dataclass_fields__'):
            assert value.__class__.__module__ == 'app.application.models'
            for field in value.__dataclass_fields__:
                check(getattr(value, field))
        elif isinstance(value, tuple):
            for item in value:
                check(item)
    check(state)
    with pytest.raises(FrozenInstanceError):
        state.card.question.text = 'changed'
    with pytest.raises(FrozenInstanceError):
        state.player.hp = 0


def test_create_failure_does_not_return_token(env):
    async def fail(*args, **kwargs):
        raise PersistenceFailure('storage unavailable')
    env.sessions.create = fail
    with pytest.raises(PersistenceFailure):
        start(env)
