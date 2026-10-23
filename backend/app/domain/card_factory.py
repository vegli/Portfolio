from collections.abc import Sequence, Set
from random import Random
from uuid import UUID, uuid4

from app.domain.card import CardRarity, CardTemplate, DrawnCard
from app.domain.effect import Effect, EffectDefinition, EffectRarity, EffectTrigger
from app.domain.question import Question


_RARITY_WEIGHTS = {CardRarity.COMMON: 70, CardRarity.RARE: 20, CardRarity.EPIC: 10}
_EFFECT_RARITIES = {
    CardRarity.COMMON: (EffectRarity.COMMON,),
    CardRarity.RARE: (EffectRarity.RARE,),
    CardRarity.EPIC: (EffectRarity.RARE, EffectRarity.EPIC),
}


class CardFactory:
    def __init__(self, rng: Random) -> None:
        if not isinstance(rng, Random):
            raise TypeError("rng must be a random.Random instance")
        self._rng = rng

    def draw(
        self,
        questions: Sequence[Question],
        templates: Sequence[CardTemplate],
        effect_definitions: Sequence[EffectDefinition],
        used_question_ids: Set[UUID],
    ) -> DrawnCard | None:
        """Draw a card, return None for exhaustion, or reject infeasible configuration."""
        self._validate_catalog(questions, Question)
        self._validate_catalog(templates, CardTemplate)
        self._validate_catalog(effect_definitions, EffectDefinition)
        if not isinstance(used_question_ids, Set):
            raise TypeError("used question IDs must be a set")
        if any(not isinstance(value, UUID) for value in used_question_ids):
            raise TypeError("used question IDs must contain UUID values")

        unused = tuple(question for question in questions if question.id not in used_question_ids)
        eligible = []
        for template in templates:
            compatible = tuple(q for q in unused if template.supports_difficulty(q.difficulty))
            if compatible:
                eligible.append((template, compatible))
        if not eligible:
            return None

        for template, _ in eligible:
            for trigger, budget in (
                (EffectTrigger.CORRECT, template.positive_effect_budget),
                (EffectTrigger.INCORRECT, template.negative_effect_budget),
            ):
                if budget and not self._eligible_effects(template, trigger, budget, effect_definitions):
                    raise ValueError(f"template {template.id} has no feasible {trigger.value} effects")

        rarities = tuple(rarity for rarity in CardRarity
                         if any(template.rarity is rarity for template, _ in eligible))
        ticket = self._rng.randrange(sum(_RARITY_WEIGHTS[rarity] for rarity in rarities))
        rarity = rarities[-1]
        for candidate in rarities:
            if ticket < _RARITY_WEIGHTS[candidate]:
                rarity = candidate
                break
            ticket -= _RARITY_WEIGHTS[candidate]
        template, compatible = self._rng.choice(
            [(template, pool) for template, pool in eligible if template.rarity is rarity]
        )
        question = self._rng.choice(compatible)
        positive = self._roll_effects(
            template, EffectTrigger.CORRECT, template.positive_effect_budget, effect_definitions,
        )
        negative = self._roll_effects(
            template, EffectTrigger.INCORRECT, template.negative_effect_budget, effect_definitions,
        )
        return DrawnCard(uuid4(), template, question, positive + negative)

    @staticmethod
    def _validate_catalog(
        values: Sequence[Question | CardTemplate | EffectDefinition], expected_type: type,
    ) -> None:
        if not isinstance(values, Sequence):
            raise TypeError("catalogs must be sequences")
        ids = set()
        for value in values:
            if not isinstance(value, expected_type):
                raise TypeError(f"catalog must contain {expected_type.__name__} values")
            if value.id in ids:
                raise ValueError(f"duplicate {expected_type.__name__} ID: {value.id}")
            ids.add(value.id)

    @staticmethod
    def _eligible_effects(
        template: CardTemplate, trigger: EffectTrigger, budget: int,
        definitions: Sequence[EffectDefinition],
    ) -> tuple[EffectDefinition, ...]:
        return tuple(definition for definition in definitions
                     if definition.trigger is trigger
                     and definition.rarity in _EFFECT_RARITIES[template.rarity]
                     and definition.cost <= budget)

    def _roll_effects(
        self, template: CardTemplate, trigger: EffectTrigger, budget: int,
        definitions: Sequence[EffectDefinition],
    ) -> tuple[Effect, ...]:
        if budget == 0:
            return ()
        candidates = self._eligible_effects(template, trigger, budget, definitions)
        target = self._rng.randint(1, min(3, len({effect.type for effect in candidates})))
        rolled = []
        for _ in range(target):
            if not candidates:
                break
            ticket = self._rng.randrange(sum(effect.weight for effect in candidates))
            selected = candidates[-1]
            for candidate in candidates:
                if ticket < candidate.weight:
                    selected = candidate
                    break
                ticket -= candidate.weight
            rolled.append(Effect(selected.type, selected.value, selected.trigger))
            budget -= selected.cost
            candidates = tuple(effect for effect in candidates
                               if effect.cost <= budget and effect.type is not selected.type)
        return tuple(rolled)
