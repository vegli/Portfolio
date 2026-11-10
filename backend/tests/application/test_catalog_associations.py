from dataclasses import replace
from uuid import uuid4

import pytest

from app.application.models import GameCatalogs
from app.domain.effect import EffectDefinition, EffectRarity, EffectTrigger, EffectType
from .conftest import run, start, submit


def test_start_and_next_forward_template_associations(env):
    allowed = EffectDefinition(uuid4(), EffectType.HP, 10, EffectTrigger.CORRECT, EffectRarity.COMMON, 1, 1)
    forbidden = replace(allowed, id=uuid4(), value=20, weight=1000000)
    template = replace(env.catalogs.catalogs.templates[0], positive_effect_budget=1)
    env.catalogs.catalogs = replace(env.catalogs.catalogs, templates=(template,),
                                   effect_definitions=(forbidden, allowed),
                                   template_effect_ids={template.id: frozenset({allowed.id})})
    game = start(env)
    assert [e.value for e in game.state.card.effects] == [10]
    run(submit(env, game))
    next_state = run(env.next.execute(game.state.id, game.token))
    assert [e.value for e in next_state.card.effects] == [10]


def test_catalog_copies_and_freezes_associations():
    template_id, effect_id = uuid4(), uuid4()
    source = {template_id: {effect_id}}
    catalog = GameCatalogs((), (), (), source)
    source[template_id].clear()
    source.clear()
    assert catalog.template_effect_ids[template_id] == frozenset({effect_id})
    with pytest.raises(TypeError):
        catalog.template_effect_ids[template_id] = frozenset()
