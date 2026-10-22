from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from app.domain.effect import Effect, EffectTrigger
from app.domain.question import Question


class CardRarity(StrEnum):
    COMMON = "common"
    RARE = "rare"
    EPIC = "epic"


@dataclass(frozen=True)
class CardTemplate:
    id: UUID
    rarity: CardRarity
    min_difficulty: int
    max_difficulty: int
    positive_effect_budget: int
    negative_effect_budget: int

    def __post_init__(self) -> None:
        self._validate_types()
        self._validate_difficulty_bounds()
        self._validate_budgets()

    def _validate_types(self) -> None:
        if not isinstance(self.rarity, CardRarity):
            raise TypeError("rarity must be a CardRarity")
        for value in (self.min_difficulty, self.max_difficulty,
                      self.positive_effect_budget, self.negative_effect_budget):
            if type(value) is not int:
                raise TypeError("difficulty bounds and budgets must be integers")

    def _validate_difficulty_bounds(self) -> None:
        if not 1 <= self.min_difficulty <= self.max_difficulty <= 5:
            raise ValueError("difficulty bounds must be ordered within 1 to 5")

    def _validate_budgets(self) -> None:
        if self.positive_effect_budget < 0 or self.negative_effect_budget < 0:
            raise ValueError("effect budgets cannot be negative")

    def supports_difficulty(self, difficulty: int) -> bool:
        return self.min_difficulty <= difficulty <= self.max_difficulty


@dataclass(frozen=True)
class DrawnCard:
    id: UUID
    template: CardTemplate
    question: Question
    effects: tuple[Effect, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "effects", tuple(self.effects))
        self._validate_question_compatibility()
        self._validate_effect_types()
        self._validate_effect_presence()

    def _validate_question_compatibility(self) -> None:
        if not self.template.supports_difficulty(self.question.difficulty):
            raise ValueError("question difficulty is incompatible with template")

    def _validate_effect_types(self) -> None:
        effect_keys = {(effect.trigger, effect.type) for effect in self.effects}
        if len(effect_keys) != len(self.effects):
            raise ValueError("effect types must be distinct within each outcome")

    def _validate_effect_presence(self) -> None:
        for trigger, budget in (
            (EffectTrigger.CORRECT, self.template.positive_effect_budget),
            (EffectTrigger.INCORRECT, self.template.negative_effect_budget),
        ):
            has_effects = any(effect.trigger is trigger for effect in self.effects)
            if has_effects != (budget > 0):
                raise ValueError("effects must be present exactly when budget is positive")
