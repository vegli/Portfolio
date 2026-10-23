from fractions import Fraction

import pytest

from app.domain.streak_policy import StreakPolicy


@pytest.mark.parametrize("streak", [0, 1, 2, 3, 4, 5, 1000])
def test_next_streak(streak: int) -> None:
    assert StreakPolicy.next_streak(streak, True) == streak + 1
    assert StreakPolicy.next_streak(streak, False) == 0


@pytest.mark.parametrize("streak,expected", [
    (0, Fraction(1)), (1, Fraction(1)), (2, Fraction(1)),
    (3, Fraction(3, 2)), (4, Fraction(3, 2)),
    (5, Fraction(2)), (1000, Fraction(2)),
])
def test_multiplier_boundaries(streak: int, expected: Fraction) -> None:
    assert StreakPolicy.multiplier(streak) == expected


@pytest.mark.parametrize("streak", [True, 1.5, "1"])
def test_streak_requires_integer(streak: object) -> None:
    with pytest.raises(TypeError):
        StreakPolicy.multiplier(streak)
    with pytest.raises(TypeError):
        StreakPolicy.next_streak(streak, True)


def test_negative_streak_rejected() -> None:
    with pytest.raises(ValueError):
        StreakPolicy.multiplier(-1)
    with pytest.raises(ValueError):
        StreakPolicy.next_streak(-1, False)


@pytest.mark.parametrize("is_correct", [0, 1, "true", None])
def test_correctness_requires_boolean(is_correct: object) -> None:
    with pytest.raises(TypeError):
        StreakPolicy.next_streak(0, is_correct)
