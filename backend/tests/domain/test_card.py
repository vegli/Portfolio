from dataclasses import FrozenInstanceError, replace
from uuid import uuid4

import pytest

from app.domain.card import CardRarity, CardTemplate, DrawnCard
from app.domain.effect import Effect, EffectTrigger, EffectType
from app.domain.question import Question


@pytest.fixture
def template() -> CardTemplate:
    return CardTemplate(uuid4(), CardRarity.COMMON, 2, 4, 0, 0)


@pytest.mark.parametrize("difficulty,expected", [(1, False), (2, True), (4, True), (5, False)])
def test_compatibility(template: CardTemplate, difficulty: int, expected: bool) -> None:
    assert template.supports_difficulty(difficulty) is expected


@pytest.mark.parametrize("minimum,maximum", [(0, 3), (1, 6), (4, 2)])
def test_invalid_bounds(template: CardTemplate, minimum: int, maximum: int) -> None:
    with pytest.raises(ValueError):
        replace(template, min_difficulty=minimum, max_difficulty=maximum)


@pytest.mark.parametrize("field", ["positive_effect_budget", "negative_effect_budget"])
def test_negative_budget(template: CardTemplate, field: str) -> None:
    with pytest.raises(ValueError):
        replace(template, **{field: -1})


@pytest.mark.parametrize("field", ["min_difficulty", "max_difficulty", "positive_effect_budget", "negative_effect_budget"])
@pytest.mark.parametrize("value", [True, 2.5])
def test_integer_template_values(template: CardTemplate, field: str, value: object) -> None:
    with pytest.raises(TypeError):
        replace(template, **{field: value})


def test_card_compatibility(template: CardTemplate, question: Question) -> None:
    with pytest.raises(ValueError):
        DrawnCard(uuid4(), template, replace(question, difficulty=5), ())


@pytest.mark.parametrize("trigger,field,value", [
    (EffectTrigger.CORRECT, "positive_effect_budget", 10),
    (EffectTrigger.INCORRECT, "negative_effect_budget", -10),
])
def test_outcome_budget_presence(template: CardTemplate, question: Question,
                                trigger: EffectTrigger, field: str, value: int) -> None:
    effects = (Effect(EffectType.HP, value, trigger),)
    with pytest.raises(ValueError):
        DrawnCard(uuid4(), template, question, effects)
    funded = replace(template, **{field: 100})
    with pytest.raises(ValueError):
        DrawnCard(uuid4(), funded, question, ())
    assert DrawnCard(uuid4(), funded, question, effects).effects == effects


def test_duplicate_type_per_outcome(template: CardTemplate, question: Question) -> None:
    template = replace(template, positive_effect_budget=4, negative_effect_budget=4)
    positive = Effect(EffectType.HP, 10, EffectTrigger.CORRECT)
    negative = Effect(EffectType.HP, -10, EffectTrigger.INCORRECT)
    card = DrawnCard(uuid4(), template, question, (positive, negative))
    with pytest.raises(ValueError):
        replace(card, effects=(positive, positive, negative))


def test_card_and_template_immutable(template: CardTemplate, question: Question) -> None:
    effects = []
    card = DrawnCard(uuid4(), template, question, effects)
    effects.append(Effect(EffectType.HP, 10, EffectTrigger.CORRECT))
    assert card.effects == ()
    with pytest.raises(FrozenInstanceError):
        card.question = question
    with pytest.raises(FrozenInstanceError):
        template.positive_effect_budget = 1


def test_template_rarity(template: CardTemplate) -> None:
    with pytest.raises(TypeError):
        replace(template, rarity="common")
