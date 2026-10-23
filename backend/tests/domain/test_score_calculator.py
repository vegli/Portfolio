from dataclasses import replace

import pytest

from app.domain.effect import Effect, EffectTrigger, EffectType
from app.domain.player import PlayerState
from app.domain.score_calculator import ScoreCalculator
from app.domain.streak_policy import StreakPolicy


@pytest.mark.parametrize("difficulty,awards", [
    (1, (10, 15, 20)), (2, (15, 23, 30)), (3, (20, 30, 40)),
    (4, (25, 38, 50)), (5, (30, 45, 60)),
])
@pytest.mark.parametrize("streak,tier", [(1, 0), (2, 0), (3, 1), (4, 1), (5, 2), (1000, 2)])
def test_base_awards_round_half_up(
    difficulty: int, awards: tuple[int, ...], streak: int, tier: int,
) -> None:
    result = ScoreCalculator.calculate(difficulty, True, streak)
    assert result == awards[tier]
    assert type(result) is int


@pytest.mark.parametrize("difficulty", range(1, 6))
def test_incorrect_answer_awards_no_base_points(difficulty: int) -> None:
    assert ScoreCalculator.calculate(difficulty, False, 0) == 0


@pytest.mark.parametrize("current,expected", [(1, 20), (2, 30), (3, 30), (4, 40)])
def test_increment_before_calculation(current: int, expected: int) -> None:
    streak = StreakPolicy.next_streak(current, True)
    assert ScoreCalculator.calculate(3, True, streak) == expected


@pytest.mark.parametrize("is_correct,streak,expected", [(True, 5, 55), (False, 0, -30)])
def test_only_matching_score_effects_apply(
    is_correct: bool, streak: int, expected: int,
) -> None:
    effects = (
        Effect(EffectType.SCORE, 15, EffectTrigger.CORRECT),
        Effect(EffectType.SCORE, -30, EffectTrigger.INCORRECT),
        Effect(EffectType.HP, 10, EffectTrigger.CORRECT),
        Effect(EffectType.HP, -20, EffectTrigger.INCORRECT),
        Effect(EffectType.TIME, 3, EffectTrigger.CORRECT),
        Effect(EffectType.TIME, -5, EffectTrigger.INCORRECT),
    )
    assert ScoreCalculator.calculate(3, is_correct, streak, effects) == expected


def test_round_base_award_before_adding_effect() -> None:
    effects = (Effect(EffectType.SCORE, 15, EffectTrigger.CORRECT),)
    assert ScoreCalculator.calculate(2, True, 3, effects) == 38


@pytest.mark.parametrize("initial_score", [0, 10, -50])
def test_penalties_allow_negative_totals_without_mutation(initial_score: int) -> None:
    player = PlayerState(score=initial_score, correct_streak=5)
    effects = (Effect(EffectType.SCORE, -30, EffectTrigger.INCORRECT),)
    streak = StreakPolicy.next_streak(player.correct_streak, False)
    delta = ScoreCalculator.calculate(1, False, streak, effects)
    updated = replace(player, score=player.score + delta, correct_streak=streak)
    assert updated.score == initial_score - 30
    assert updated.correct_streak == 0
    assert player == PlayerState(score=initial_score, correct_streak=5)


@pytest.mark.parametrize("difficulty", [True, 1.5, "1"])
def test_difficulty_requires_integer(difficulty: object) -> None:
    with pytest.raises(TypeError):
        ScoreCalculator.calculate(difficulty, True, 1)


@pytest.mark.parametrize("difficulty", [0, 6])
def test_difficulty_bounds(difficulty: int) -> None:
    with pytest.raises(ValueError):
        ScoreCalculator.calculate(difficulty, True, 1)


@pytest.mark.parametrize("is_correct", [0, 1, "true", None])
def test_correctness_requires_boolean(is_correct: object) -> None:
    with pytest.raises(TypeError):
        ScoreCalculator.calculate(1, is_correct, 1)


@pytest.mark.parametrize("streak", [True, 1.5, "1"])
def test_streak_requires_integer(streak: object) -> None:
    with pytest.raises(TypeError):
        ScoreCalculator.calculate(1, True, streak)


@pytest.mark.parametrize("is_correct,streak", [(True, 0), (False, 1), (False, 5), (False, -1)])
def test_streak_must_reflect_answer(is_correct: bool, streak: int) -> None:
    with pytest.raises(ValueError):
        ScoreCalculator.calculate(1, is_correct, streak)
