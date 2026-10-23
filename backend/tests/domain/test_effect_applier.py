from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.domain.effect import Effect, EffectTrigger, EffectType
from app.domain.effect_applier import EffectApplier
from app.domain.game_session import GameSession
from app.domain.player import PlayerState
from app.domain.score_calculator import ScoreCalculator


@pytest.mark.parametrize("hp,value,is_correct,expected", [
    (100, 20, True, 120), (10, -20, False, -10),
    (100, -20, False, 80), (-10, 20, True, 10),
])
def test_hp_effects(hp: int, value: int, is_correct: bool, expected: int) -> None:
    trigger = EffectTrigger.CORRECT if is_correct else EffectTrigger.INCORRECT
    player = PlayerState(hp=hp, score=-50, correct_streak=4)
    updated, remaining = EffectApplier.apply(
        player, 60_000, is_correct, (Effect(EffectType.HP, value, trigger),),
    )
    assert updated == PlayerState(hp=expected, score=-50, correct_streak=4)
    assert remaining == 60_000
    assert player == PlayerState(hp=hp, score=-50, correct_streak=4)


@pytest.mark.parametrize("remaining,value,is_correct,expected", [
    (60_123, 3, True, 63_123), (60_123, -5, False, 55_123),
    (5_000, -5, False, 0), (4_999, -5, False, 0),
    (0, 3, True, 3_000), (0, -5, False, 0),
])
def test_time_effects(
    remaining: int, value: int, is_correct: bool, expected: int,
) -> None:
    trigger = EffectTrigger.CORRECT if is_correct else EffectTrigger.INCORRECT
    player = PlayerState()
    updated, time_ms = EffectApplier.apply(
        player, remaining, is_correct, (Effect(EffectType.TIME, value, trigger),),
    )
    assert time_ms == expected
    assert type(time_ms) is int
    assert updated == player


@pytest.mark.parametrize("is_correct,hp,time_ms", [(True, 110, 63_000), (False, 80, 55_000)])
def test_matching_trigger_and_score_filtering(is_correct: bool, hp: int, time_ms: int) -> None:
    effects = (
        Effect(EffectType.HP, 10, EffectTrigger.CORRECT),
        Effect(EffectType.HP, -20, EffectTrigger.INCORRECT),
        Effect(EffectType.TIME, 3, EffectTrigger.CORRECT),
        Effect(EffectType.TIME, -5, EffectTrigger.INCORRECT),
        Effect(EffectType.SCORE, 15, EffectTrigger.CORRECT),
        Effect(EffectType.SCORE, -30, EffectTrigger.INCORRECT),
    )
    player = PlayerState(score=-50, correct_streak=4)
    updated, remaining = EffectApplier.apply(player, 60_000, is_correct, effects)
    assert updated == replace(player, hp=hp)
    assert remaining == time_ms


@pytest.mark.parametrize("is_correct", [True, False])
def test_nonmatching_effects_do_nothing(is_correct: bool) -> None:
    trigger = EffectTrigger.INCORRECT if is_correct else EffectTrigger.CORRECT
    value = -3 if is_correct else 3
    effects = tuple(Effect(kind, value, trigger) for kind in EffectType)
    player = PlayerState()
    assert EffectApplier.apply(player, 123, is_correct, effects) == (player, 123)


@pytest.mark.parametrize("effects", [(), []])
def test_no_effects(effects: tuple[Effect, ...] | list[Effect]) -> None:
    player = PlayerState(hp=-10, score=-50, correct_streak=5)
    updated, remaining = EffectApplier.apply(player, 90_123, True, effects)
    assert updated == player
    assert updated is not player
    assert remaining == 90_123
    assert effects == () or effects == []


@pytest.mark.parametrize("collection_type", [tuple, list])
def test_effects_and_collections_are_unchanged(collection_type: type) -> None:
    effect = Effect(EffectType.HP, 10, EffectTrigger.CORRECT)
    effects = collection_type([effect])
    EffectApplier.apply(PlayerState(), 60_000, True, effects)
    assert effects == collection_type([effect])
    assert effects[0] is effect
    assert effect == Effect(EffectType.HP, 10, EffectTrigger.CORRECT)


def test_session_is_unchanged() -> None:
    session = GameSession(uuid4(), datetime(2026, 10, 23, tzinfo=UTC))
    snapshot = replace(session)
    effects = (Effect(EffectType.HP, 10, EffectTrigger.CORRECT),)
    updated, remaining = EffectApplier.apply(
        session.player, session.remaining_time_ms, True, effects,
    )
    assert updated.hp == 110
    assert remaining == 60_000
    assert session == snapshot


@pytest.mark.parametrize("is_correct,streak,score,hp,time_ms", [
    (True, 3, 38, 110, 63_000), (False, 0, -30, 80, 55_000),
])
def test_composition_applies_score_effects_once(
    is_correct: bool, streak: int, score: int, hp: int, time_ms: int,
) -> None:
    effects = (
        Effect(EffectType.SCORE, 15, EffectTrigger.CORRECT),
        Effect(EffectType.SCORE, -30, EffectTrigger.INCORRECT),
        Effect(EffectType.HP, 10, EffectTrigger.CORRECT),
        Effect(EffectType.HP, -20, EffectTrigger.INCORRECT),
        Effect(EffectType.TIME, 3, EffectTrigger.CORRECT),
        Effect(EffectType.TIME, -5, EffectTrigger.INCORRECT),
    )
    player = PlayerState(correct_streak=streak)
    delta = ScoreCalculator.calculate(2, is_correct, streak, effects)
    scored = replace(player, score=player.score + delta)
    updated, remaining = EffectApplier.apply(scored, 60_000, is_correct, effects)
    assert updated == PlayerState(hp=hp, score=score, correct_streak=streak)
    assert remaining == time_ms
    assert player == PlayerState(correct_streak=streak)


@pytest.mark.parametrize("player", [None, {}, 100])
def test_invalid_player(player: object) -> None:
    with pytest.raises(TypeError):
        EffectApplier.apply(player, 60_000, True)


@pytest.mark.parametrize("remaining", [True, 1.5, "1000", None])
def test_time_requires_integer(remaining: object) -> None:
    with pytest.raises(TypeError):
        EffectApplier.apply(PlayerState(), remaining, True)


def test_negative_input_time_rejected() -> None:
    with pytest.raises(ValueError):
        EffectApplier.apply(PlayerState(), -1, True)


@pytest.mark.parametrize("is_correct", [0, 1, "true", None])
def test_correctness_requires_boolean(is_correct: object) -> None:
    with pytest.raises(TypeError):
        EffectApplier.apply(PlayerState(), 60_000, is_correct)


@pytest.mark.parametrize("effects", [None, {}, "effects", {1}, (object(),), [None]])
def test_invalid_effects(effects: object) -> None:
    with pytest.raises(TypeError):
        EffectApplier.apply(PlayerState(), 60_000, True, effects)
