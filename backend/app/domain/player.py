from dataclasses import dataclass


@dataclass(frozen=True)
class PlayerState:
    hp: int = 100
    score: int = 0
    correct_streak: int = 0

    def __post_init__(self) -> None:
        for value in (self.hp, self.score, self.correct_streak):
            if type(value) is not int:
                raise TypeError("player values must be integers")
        if self.correct_streak < 0:
            raise ValueError("correct streak cannot be negative")
