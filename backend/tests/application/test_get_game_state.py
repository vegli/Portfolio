from dataclasses import asdict, replace
from datetime import timedelta
from uuid import uuid4

import pytest

from app.application.errors import ConcurrentUpdate, SessionUnavailable
from app.application.models import ExpiryPolicy
from .conftest import answered, run, start, submit


def test_active_refresh_is_read_only(env):
    game = start(env)
    before = env.sessions.records[game.state.id]
    deadline = env.sessions.deadlines[game.state.id]
    env.clock.advance(2)
    state = run(env.get.execute(game.state.id, game.token))
    assert state.remaining_time_ms == 58_000
    assert env.sessions.records[game.state.id] is before
    assert env.sessions.deadlines[game.state.id] == deadline
    assert not env.sessions.writes
    assert 'correct_answer_id' not in repr(asdict(state))


def test_new_expiration_persists_once_without_ttl_renewal(env):
    game = answered(env)
    deadline = env.sessions.deadlines[game.state.id]
    env.clock.advance(60)
    state = run(env.get.execute(game.state.id, game.token))
    assert state.game_over_reason == 'time_expired'
    assert state.last_answer_result is not None
    assert env.sessions.writes[-1][1] is ExpiryPolicy.PRESERVE
    assert env.sessions.deadlines[game.state.id] == deadline
    assert run(env.get.execute(game.state.id, game.token)) == state
    assert len(env.sessions.writes) == 2


def test_expiration_racing_time_bonus_reloads_without_overwriting(env):
    game = start(env)
    initial = env.sessions.records[game.state.id]
    env.clock.advance(60)
    async def bonus(_):
        # A concurrent answer accepted before expiry commits a time bonus first.
        from app.domain.effect import Effect, EffectTrigger, EffectType
        card = initial.session.current_card
        card = replace(card, template=replace(card.template, positive_effect_budget=1),
                       effects=(Effect(EffectType.TIME, 10, EffectTrigger.CORRECT),))
        session = replace(initial.session, current_card=card)
        session = session.submit_answer(card.id, card.question.correct_answer_id,
                                       now=env.clock.now() - timedelta(seconds=1))
        env.sessions.records[game.state.id] = replace(initial, session=session, version=1)
    env.sessions.before_cas = bonus
    state = run(env.get.execute(game.state.id, game.token))
    assert state.status == 'active'
    assert state.remaining_time_ms == 10_000
    assert state.last_answer_result is not None
    assert not env.sessions.writes


@pytest.mark.parametrize('operation', ['get', 'next', 'submit'])
@pytest.mark.parametrize('credential', ['invalid', 'missing', 'expired'])
def test_unavailable_is_consistent_and_has_no_effects(env, operation, credential):
    game = start(env)
    token = game.token
    session_id = game.state.id
    if credential == 'invalid':
        token = 'bad'
    elif credential == 'missing':
        session_id = uuid4()
    else:
        env.clock.advance(900)
    if operation == 'submit':
        call = env.submit.execute(session_id, token, card_id=game.state.card.id,
                                  answer_option_id=game.state.card.question.options[0].id)
    else:
        call = getattr(env, operation).execute(session_id, token)
    with pytest.raises(SessionUnavailable):
        run(call)
    assert not env.sessions.writes
    assert env.catalogs.loads == 1
    assert env.sessions.attempts == 0


@pytest.mark.parametrize('operation', ['get', 'next', 'submit'])
def test_expired_key_during_cas_is_not_resurrected(env, operation):
    game = answered(env) if operation == 'next' else start(env)
    if operation == 'get':
        env.clock.advance(60)
    async def expire(_):
        env.clock.advance(900)
    env.sessions.before_cas = expire
    if operation == 'submit':
        call = submit(env, game)
    else:
        call = getattr(env, operation).execute(game.state.id, game.token)
    with pytest.raises(SessionUnavailable):
        run(call)
    assert game.state.id not in env.sessions.records


def test_get_retry_reauthorizes(env):
    game = start(env)
    env.clock.advance(60)
    async def conflict(_):
        stored = env.sessions.records[game.state.id]
        env.sessions.records[game.state.id] = replace(stored, version=1, token_verifier=b'changed')
    env.sessions.before_cas = conflict
    with pytest.raises(SessionUnavailable):
        run(env.get.execute(game.state.id, game.token))
    assert not env.sessions.writes


def test_get_conflicts_stop_after_three_attempts(env):
    game = start(env)
    env.clock.advance(60)
    async def conflict(_):
        stored = env.sessions.records[game.state.id]
        env.sessions.records[game.state.id] = replace(stored, version=stored.version + 1)
        env.sessions.before_cas = conflict
    env.sessions.before_cas = conflict
    with pytest.raises(ConcurrentUpdate):
        run(env.get.execute(game.state.id, game.token))
    assert env.sessions.attempts == 3
    assert not env.sessions.writes


def test_rejected_expired_submission_does_not_claim_retained_feedback(env):
    game = answered(env)
    env.clock.advance(60)
    result = run(submit(env, game))
    assert not result.accepted
    assert result.state.game_over_reason == 'time_expired'
    assert result.state.last_answer_result.card_id == game.state.card.id
    assert result.state.player.score == 15


def test_get_conflict_with_committed_finish_returns_latest_without_write(env):
    game = start(env)
    env.clock.advance(60)
    async def finish(candidate):
        stored = env.sessions.records[game.state.id]
        env.sessions.records[game.state.id] = replace(stored, session=candidate, version=1)
    env.sessions.before_cas = finish
    state = run(env.get.execute(game.state.id, game.token))
    assert state.game_over_reason == 'time_expired'
    assert env.sessions.attempts == 1
    assert not env.sessions.writes
