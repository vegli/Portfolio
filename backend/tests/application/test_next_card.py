from dataclasses import replace
from datetime import timedelta
from random import Random

import pytest

from app.application.errors import CatalogFailure, GameAlreadyFinished, InvalidGamePhase, SessionUnavailable
from app.application.models import ExpiryPolicy
from app.domain.card_factory import CardFactory
from .conftest import answered, run, start


def test_next_assigns_and_clears_feedback(env):
    game = answered(env)
    before = env.sessions.records[game.state.id].session
    env.clock.advance(1)
    result = run(env.next.execute(game.state.id, game.token))
    assert result.phase == 'awaiting_answer'
    assert result.last_answer_result is None
    assert result.card.id != before.current_card.id
    assert result.card.question.id not in before.used_question_ids
    assert env.sessions.records[game.state.id].session.used_question_ids == before.used_question_ids | {result.card.question.id}
    assert env.sessions.deadlines[game.state.id] == env.clock.now() + timedelta(minutes=15)


@pytest.mark.parametrize('condition', ['unauthorized', 'phase', 'finished', 'expired', 'missing'])
def test_guards_precede_catalog_and_randomness(env, condition):
    game = start(env)
    token = game.token
    error = None
    if condition == 'unauthorized':
        token = 'invalid'
        error = SessionUnavailable
    elif condition == 'phase':
        error = InvalidGamePhase
    elif condition == 'finished':
        stored = env.sessions.records[game.state.id]
        env.clock.advance(60)
        env.sessions.records[game.state.id] = replace(stored, session=stored.session.refresh(now=env.clock.now()))
        error = GameAlreadyFinished
    elif condition == 'missing':
        env.sessions.records.clear()
        error = SessionUnavailable
    else:
        env.clock.advance(60)
    loads, factories = env.catalogs.loads, len(env.factories)
    if error:
        with pytest.raises(error):
            run(env.next.execute(game.state.id, token))
    else:
        assert run(env.next.execute(game.state.id, token)).game_over_reason == 'time_expired'
    assert env.catalogs.loads == loads
    assert len(env.factories) == factories


def test_exhaustion_renews_and_retains_feedback(env):
    game = answered(env)
    before = env.sessions.records[game.state.id].session
    env.catalogs.catalogs = replace(env.catalogs.catalogs, questions=())
    env.clock.advance(2)
    state = run(env.next.execute(game.state.id, game.token))
    assert state.game_over_reason == 'no_questions_available'
    assert state.last_answer_result.card_id == before.last_answer_result.card_id
    assert env.sessions.writes[-1][1] is ExpiryPolicy.RENEW_ACTIVITY
    assert env.sessions.deadlines[game.state.id] == env.clock.now() + timedelta(minutes=15)


@pytest.mark.parametrize('exhausted', [False, True])
@pytest.mark.parametrize('delay_at', ['load', 'draw'])
def test_expiration_during_preparation_wins(env, exhausted, delay_at):
    game = answered(env)
    deadline = env.sessions.deadlines[game.state.id]
    if exhausted:
        env.catalogs.catalogs = replace(env.catalogs.catalogs, questions=())
    if delay_at == 'load':
        env.catalogs.on_load = lambda: env.clock.advance(60)
    else:
        class SlowFactory(CardFactory):
            def draw(self, *args):
                card = super().draw(*args)
                env.clock.advance(60)
                return card
        env.next.card_factory = lambda: SlowFactory(Random(1))
    state = run(env.next.execute(game.state.id, game.token))
    assert state.game_over_reason == 'time_expired'
    assert state.last_answer_result is not None
    assert env.sessions.deadlines[game.state.id] == deadline
    assert env.sessions.writes[-1][1] is ExpiryPolicy.PRESERVE
    assert len(env.sessions.records[game.state.id].session.used_question_ids) == 1


def test_competing_draw_exposes_only_committed_card(env):
    game = answered(env)
    committed = []
    async def competitor(_):
        committed.append(await env.next.execute(game.state.id, game.token))
    env.sessions.before_cas = competitor
    with pytest.raises(InvalidGamePhase):
        run(env.next.execute(game.state.id, game.token))
    stored = env.sessions.records[game.state.id]
    assert stored.session.current_card.id == committed[0].card.id
    assert len(stored.session.used_question_ids) == 2
    assert len(env.sessions.writes) == 2  # One answer and one draw.
    assert env.catalogs.loads == 3  # Start and two competing preparations.


def test_retry_discards_candidate_and_rechecks_auth_before_catalogs(env):
    game = answered(env)
    async def conflict(_):
        stored = env.sessions.records[game.state.id]
        env.sessions.records[game.state.id] = replace(stored, version=stored.version + 1,
                                                     token_verifier=b'changed')
    env.sessions.before_cas = conflict
    with pytest.raises(SessionUnavailable):
        run(env.next.execute(game.state.id, game.token))
    assert env.catalogs.loads == 2
    assert len(env.sessions.writes) == 1


def test_retry_draws_again_only_after_valid_reload(env):
    game = answered(env)
    candidates = []
    async def conflict(candidate):
        candidates.append(candidate.current_card.id)
        stored = env.sessions.records[game.state.id]
        env.sessions.records[game.state.id] = replace(stored, version=stored.version + 1)
    env.sessions.before_cas = conflict
    state = run(env.next.execute(game.state.id, game.token))
    assert state.card.id != candidates[0]
    assert len(env.sessions.records[game.state.id].session.used_question_ids) == 2
    assert env.catalogs.loads == 3
    assert len(env.factories) == 2  # One per start/next execution, not per retry.


def test_invalid_catalog_does_not_finish_or_write(env):
    game = answered(env)
    template = replace(env.catalogs.catalogs.templates[0], positive_effect_budget=1)
    env.catalogs.catalogs = replace(env.catalogs.catalogs, templates=(template,))
    with pytest.raises(CatalogFailure):
        run(env.next.execute(game.state.id, game.token))
    assert len(env.sessions.writes) == 1


def test_next_retries_stop_after_three_conflicts(env):
    from app.application.errors import ConcurrentUpdate
    game = answered(env)
    async def conflict(_):
        stored = env.sessions.records[game.state.id]
        env.sessions.records[game.state.id] = replace(stored, version=stored.version + 1)
        env.sessions.before_cas = conflict
    env.sessions.before_cas = conflict
    with pytest.raises(ConcurrentUpdate):
        run(env.next.execute(game.state.id, game.token))
    assert env.sessions.attempts == 4  # Answer plus three failed next-card attempts.
    assert len(env.sessions.writes) == 1
