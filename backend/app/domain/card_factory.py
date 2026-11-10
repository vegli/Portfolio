from collections.abc import Mapping, Sequence, Set
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
        *,
        template_effect_ids: Mapping[UUID, frozenset[UUID]] | None = None,
    ) -> DrawnCard | None:
        """Draw a card, return None for exhaustion, or reject infeasible configuration."""
        self._validate_catalog(questions, Question)
        self._validate_catalog(templates, CardTemplate)
        self._validate_catalog(effect_definitions, EffectDefinition)
        if not isinstance(used_question_ids, Set):
            raise TypeError("used question IDs must be a set")
        if any(not isinstance(value, UUID) for value in used_question_ids):
            raise TypeError("used question IDs must contain UUID values")

        pools = self._effect_pools(templates, effect_definitions, template_effect_ids)
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
                if budget and not self._eligible_effects(template, trigger, budget, pools[template.id]):
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
            template, EffectTrigger.CORRECT, template.positive_effect_budget, pools[template.id],
        )
        negative = self._roll_effects(
            template, EffectTrigger.INCORRECT, template.negative_effect_budget, pools[template.id],
        )
        return DrawnCard(uuid4(), template, question, positive + negative)

    @staticmethod
    def _effect_pools(
        templates: Sequence[CardTemplate], definitions: Sequence[EffectDefinition],
        associations: Mapping[UUID, frozenset[UUID]] | None,
    ) -> dict[UUID, tuple[EffectDefinition, ...]]:
        if associations is None:
            return {template.id: tuple(definitions) for template in templates}
        if not isinstance(associations, Mapping):
            raise TypeError("template effect associations must be a mapping")
        template_ids = {template.id for template in templates}
        effect_ids = {definition.id for definition in definitions}
        if set(associations) != template_ids:
            raise ValueError("effect associations must include exactly the catalog templates")
        for ids in associations.values():
            if not isinstance(ids, Set) or any(not isinstance(id, UUID) for id in ids):
                raise TypeError("associated effect IDs must be UUID sets")
            if not ids <= effect_ids:
                raise ValueError("effect association references an unknown effect")
        return {
            template.id: tuple(d for d in definitions if d.id in associations[template.id])
            for template in templates
        }

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
