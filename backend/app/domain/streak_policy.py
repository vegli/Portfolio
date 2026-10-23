from fractions import Fraction


class StreakPolicy:
    @staticmethod
    def next_streak(current_streak: int, is_correct: bool) -> int:
        StreakPolicy._validate_streak(current_streak)
        if type(is_correct) is not bool:
            raise TypeError("is_correct must be a boolean")
        return current_streak + 1 if is_correct else 0

    @staticmethod
    def multiplier(correct_streak: int) -> Fraction:
        StreakPolicy._validate_streak(correct_streak)
        if correct_streak >= 5:
            return Fraction(2)
        if correct_streak >= 3:
            return Fraction(3, 2)
        return Fraction(1)

    @staticmethod
    def _validate_streak(streak: int) -> None:
        if type(streak) is not int:
            raise TypeError("correct streak must be an integer")
        if streak < 0:
            raise ValueError("correct streak cannot be negative")
