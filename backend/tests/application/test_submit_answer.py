from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import pytest

from app.application.errors import (
    ConcurrentUpdate, GameAlreadyFinished, InvalidAnswerOption, InvalidGamePhase,
    PersistenceFailure, SessionUnavailable, StaleCard,
)
from app.application.models import ExpiryPolicy
from app.domain.effect import Effect, EffectTrigger, EffectType
from .conftest import answered, run, start, submit


def test_answer_delegates_to_domain_and_renews_ttl(env):
    game = start(env)
    before = env.sessions.records[game.state.id].session
    env.clock.advance(2)
    expected = before.submit_answer(before.current_card.id,
        before.current_card.question.correct_answer_id, now=env.clock.now())
    result = run(submit(env, game))
    assert result.accepted
    assert result.state.player.score == 15
    assert env.sessions.records[game.state.id].session == expected
    assert env.sessions.writes[-1][1] is ExpiryPolicy.RENEW_ACTIVITY
    assert env.sessions.deadlines[game.state.id] == env.clock.now() + timedelta(minutes=15)
    assert result.state.last_answer_result.correct_answer_id == before.current_card.question.correct_answer_id


def test_duplicate_cannot_score_or_renew(env):
    game = answered(env)
    deadline = env.sessions.deadlines[game.state.id]
    env.clock.advance(1)
    with pytest.raises(InvalidGamePhase):
        run(submit(env, game))
    assert len(env.sessions.writes) == 1
    assert env.sessions.records[game.state.id].session.player.score == 15
    assert env.sessions.deadlines[game.state.id] == deadline


@pytest.mark.parametrize('kind,error', [('card', StaleCard), ('option', InvalidAnswerOption)])
def test_invalid_ids(env, kind, error):
    game = start(env)
    card = env.sessions.records[game.state.id].session.current_card
    with pytest.raises(error):
        run(env.submit.execute(game.state.id, game.token,
            card_id=uuid4() if kind == 'card' else card.id,
            answer_option_id=uuid4() if kind == 'option' else card.question.correct_answer_id))
    assert not env.sessions.writes


def test_expiration_before_semantic_validation_preserves_ttl(env):
    game = start(env)
    deadline = env.sessions.deadlines[game.state.id]
    env.clock.advance(60)
    result = run(env.submit.execute(game.state.id, game.token,
        card_id=uuid4(), answer_option_id=uuid4()))
    assert not result.accepted
    assert result.state.game_over_reason == 'time_expired'
    assert result.state.last_answer_result is None
    assert result.state.player.score == 0
    assert env.sessions.deadlines[game.state.id] == deadline
    assert env.sessions.writes[-1][1] is ExpiryPolicy.PRESERVE
    with pytest.raises(GameAlreadyFinished):
        run(submit(env, game))


def test_competing_answer_commits_once(env):
    game = start(env)
    async def competitor(_):
        result = await submit(env, game)
        assert result.accepted
    env.sessions.before_cas = competitor
    with pytest.raises(InvalidGamePhase):
        run(submit(env, game))
    assert len(env.sessions.writes) == 1
    assert env.sessions.records[game.state.id].session.player.score == 15
    assert env.tokens.checks == 3


def test_conflict_retries_with_fresh_time(env):
    game = start(env)
    async def conflict(_):
        stored = env.sessions.records[game.state.id]
        env.sessions.records[game.state.id] = replace(stored, version=stored.version + 1)
        env.clock.advance(60)
    env.sessions.before_cas = conflict
    result = run(submit(env, game))
    assert not result.accepted
    assert result.state.game_over_reason == 'time_expired'
    assert env.sessions.attempts == 2


@pytest.mark.parametrize('missing', [False, True])
def test_retries_reauthorize_or_detect_missing(env, missing):
    game = start(env)
    async def conflict(_):
        if missing:
            env.sessions.records.pop(game.state.id)
        else:
            stored = env.sessions.records[game.state.id]
            env.sessions.records[game.state.id] = replace(stored, version=stored.version + 1,
                                                         token_verifier=b'changed')
    env.sessions.before_cas = conflict
    with pytest.raises(SessionUnavailable):
        run(submit(env, game))
    assert not env.sessions.writes


@pytest.mark.parametrize('disappear_on_last', [False, True])
def test_three_total_attempts_and_final_missing_detection(env, disappear_on_last):
    game = start(env)
    async def conflict(_):
        stored = env.sessions.records[game.state.id]
        env.sessions.records[game.state.id] = replace(stored, version=stored.version + 1)
        if env.sessions.attempts == 3 and disappear_on_last:
            env.sessions.records.pop(game.state.id)
        env.sessions.before_cas = conflict
    env.sessions.before_cas = conflict
    with pytest.raises(SessionUnavailable if disappear_on_last else ConcurrentUpdate):
        run(submit(env, game))
    assert env.sessions.attempts == 3
    assert env.tokens.checks == (3 if disappear_on_last else 4)
    assert not env.sessions.writes


def test_operational_failure_is_not_retried(env):
    game = start(env)
    async def fail(_):
        raise PersistenceFailure('storage unavailable')
    env.sessions.before_cas = fail
    with pytest.raises(PersistenceFailure):
        run(submit(env, game))
    assert env.sessions.attempts == 1


def test_terminal_accepted_answer_renews_and_preserves_hp_priority(env):
    game = start(env)
    stored = env.sessions.records[game.state.id]
    card = stored.session.current_card
    card = replace(card, template=replace(card.template, negative_effect_budget=2), effects=(
        Effect(EffectType.HP, -100, EffectTrigger.INCORRECT),
        Effect(EffectType.TIME, -60, EffectTrigger.INCORRECT),
    ))
    env.sessions.records[game.state.id] = replace(stored, session=replace(stored.session, current_card=card))
    env.clock.advance(1)
    result = run(submit(env, game, correct=False))
    assert result.accepted
    assert result.state.game_over_reason == 'hp_depleted'
    assert result.state.last_answer_result.is_correct is False
    assert env.sessions.writes[-1][1] is ExpiryPolicy.RENEW_ACTIVITY
