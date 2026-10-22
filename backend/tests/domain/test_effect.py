from dataclasses import FrozenInstanceError, replace
from uuid import uuid4

import pytest

from app.domain.effect import Effect, EffectDefinition, EffectRarity, EffectTrigger, EffectType


@pytest.mark.parametrize("effect_type", list(EffectType))
@pytest.mark.parametrize("trigger,value", [(EffectTrigger.CORRECT, 10), (EffectTrigger.INCORRECT, -10)])
def test_valid_effect(effect_type: EffectType, trigger: EffectTrigger, value: int) -> None:
    assert Effect(effect_type, value, trigger).value == value


@pytest.mark.parametrize("trigger,value", [
    (EffectTrigger.CORRECT, 0), (EffectTrigger.CORRECT, -1),
    (EffectTrigger.INCORRECT, 0), (EffectTrigger.INCORRECT, 1),
])
def test_invalid_sign(trigger: EffectTrigger, value: int) -> None:
    with pytest.raises(ValueError):
        Effect(EffectType.HP, value, trigger)
    with pytest.raises(ValueError):
        EffectDefinition(uuid4(), EffectType.HP, value, trigger, EffectRarity.COMMON, 1, 1)


@pytest.fixture
def definition() -> EffectDefinition:
    return EffectDefinition(uuid4(), EffectType.TIME, 3, EffectTrigger.CORRECT,
                            EffectRarity.COMMON, 1, 70)


@pytest.mark.parametrize("field", ["cost", "weight"])
@pytest.mark.parametrize("value", [0, -1])
def test_positive_definition_values(definition: EffectDefinition, field: str, value: int) -> None:
    with pytest.raises(ValueError):
        replace(definition, **{field: value})


@pytest.mark.parametrize("field", ["value", "cost", "weight"])
@pytest.mark.parametrize("value", [True, 1.5, "1"])
def test_integer_definition_values(definition: EffectDefinition, field: str, value: object) -> None:
    with pytest.raises(TypeError):
        replace(definition, **{field: value})


@pytest.mark.parametrize("field,value", [("type", "hp"), ("trigger", "correct"), ("rarity", "rare")])
def test_enum_values(definition: EffectDefinition, field: str, value: str) -> None:
    with pytest.raises(TypeError):
        replace(definition, **{field: value})


def test_immutable_effects(definition: EffectDefinition) -> None:
    with pytest.raises(FrozenInstanceError):
        definition.cost = 2
    effect = Effect(definition.type, definition.value, definition.trigger)
    with pytest.raises(FrozenInstanceError):
        effect.value = 5
