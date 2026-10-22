from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class EffectType(StrEnum):
    HP = "hp"
    SCORE = "score"
    TIME = "time"


class EffectTrigger(StrEnum):
    CORRECT = "correct"
    INCORRECT = "incorrect"


class EffectRarity(StrEnum):
    COMMON = "common"
    RARE = "rare"
    EPIC = "epic"


@dataclass(frozen=True)
class Effect:
    type: EffectType
    value: int
    trigger: EffectTrigger

    def __post_init__(self) -> None:
        self._validate_types()
        self._validate_trigger_value()

    def _validate_types(self) -> None:
        if not isinstance(self.type, EffectType):
            raise TypeError("type must be an EffectType")
        if not isinstance(self.trigger, EffectTrigger):
            raise TypeError("trigger must be an EffectTrigger")
        if type(self.value) is not int:
            raise TypeError("effect value must be an integer")

    def _validate_trigger_value(self) -> None:
        if self.trigger is EffectTrigger.CORRECT and self.value <= 0:
            raise ValueError("correct-answer effects must be positive")
        if self.trigger is EffectTrigger.INCORRECT and self.value >= 0:
            raise ValueError("incorrect-answer effects must be negative")


@dataclass(frozen=True)
class EffectDefinition:
    id: UUID
    type: EffectType
    value: int
    trigger: EffectTrigger
    rarity: EffectRarity
    cost: int
    weight: int

    def __post_init__(self) -> None:
        Effect(self.type, self.value, self.trigger)
        if not isinstance(self.rarity, EffectRarity):
            raise TypeError("rarity must be an EffectRarity")
        self._validate_cost_and_weight()

    def _validate_cost_and_weight(self) -> None:
        for value in (self.cost, self.weight):
            if type(value) is not int:
                raise TypeError("effect cost and weight must be integers")
            if value <= 0:
                raise ValueError("effect cost and weight must be positive")
