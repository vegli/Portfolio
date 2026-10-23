from fractions import Fraction

from app.domain.effect import Effect, EffectTrigger, EffectType
from app.domain.streak_policy import StreakPolicy


class ScoreCalculator:
    @staticmethod
    def calculate(
        difficulty: int,
        is_correct: bool,
        correct_streak: int,
        effects: tuple[Effect, ...] = (),
    ) -> int:
        """Return the score delta using the already updated correct streak."""
        if type(difficulty) is not int:
            raise TypeError("difficulty must be an integer")
        if not 1 <= difficulty <= 5:
            raise ValueError("difficulty must be between 1 and 5")
        if type(is_correct) is not bool:
            raise TypeError("is_correct must be a boolean")
        multiplier = StreakPolicy.multiplier(correct_streak)
        if is_correct != (correct_streak > 0):
            raise ValueError("correct streak must reflect the evaluated answer")

        base_award = 0
        if is_correct:
            base_points = {1: 10, 2: 15, 3: 20, 4: 25, 5: 30}
            exact_award = base_points[difficulty] * multiplier
            # Base awards are positive; adding half then dividing rounds ties up.
            rounded_award = exact_award + Fraction(1, 2)
            base_award = rounded_award.numerator // rounded_award.denominator

        trigger = EffectTrigger.CORRECT if is_correct else EffectTrigger.INCORRECT
        return base_award + sum(
            effect.value for effect in effects
            if effect.type is EffectType.SCORE and effect.trigger is trigger
        )
