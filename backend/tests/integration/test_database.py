import asyncio
from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import insert, inspect, select
from sqlalchemy.exc import IntegrityError

from app.persistence.models import AnswerOption, Base, CardTemplate, CardTemplateEffect, Effect, Question

from .support import in_schema, migration


def test_migration_round_trip(database_url):
    async def check(connection):
        differences = await connection.run_sync(
            lambda c: compare_metadata(MigrationContext.configure(c), Base.metadata)
        )
        assert differences == []
        await connection.run_sync(migration, "downgrade", "base")
        assert await connection.run_sync(lambda c: inspect(c).get_table_names()) == ["alembic_version"]
        await connection.run_sync(migration, "upgrade", "head")
        assert set(await connection.run_sync(lambda c: inspect(c).get_table_names())) == set(Base.metadata.tables) | {"alembic_version"}
    asyncio.run(in_schema(database_url, check))


@pytest.mark.parametrize("case", [
    "difficulty", "category", "position", "duplicate_position", "second_correct",
    "missing_question", "template_range", "template_budget", "template_rarity",
    "effect_type", "effect_trigger", "effect_rarity", "effect_sign", "effect_cost",
    "effect_weight", "duplicate_template_code", "duplicate_effect_code",
    "duplicate_association", "missing_template", "missing_effect",
])
def test_constraints(database_url, case):
    async def check(connection):
        qid, tid, eid = uuid4(), uuid4(), uuid4()
        question = dict(text="Question", category="databases", difficulty=1)
        template = dict(code="basic", name="Basic", description="", rarity="common", min_difficulty=1, max_difficulty=5, positive_effect_budget=1, negative_effect_budget=0)
        effect = dict(code="hp", description="", type="hp", trigger="correct", value=10, rarity="common", cost=1, weight=70)
        await connection.execute(insert(Question).values(id=qid, **question))
        await connection.execute(insert(CardTemplate).values(id=tid, **template))
        await connection.execute(insert(Effect).values(id=eid, **effect))
        await connection.execute(insert(AnswerOption).values(question_id=qid, text="Yes", is_correct=True, position=1))
        await connection.execute(insert(CardTemplateEffect).values(card_template_id=tid, effect_id=eid))
        if case in {"difficulty", "category"}:
            question.update({case: 0 if case == "difficulty" else "unknown"})
            statement = insert(Question).values(**question)
        elif case in {"position", "duplicate_position", "second_correct", "missing_question"}:
            statement = insert(AnswerOption).values(question_id=uuid4() if case == "missing_question" else qid, text="Other", is_correct=case == "second_correct", position=0 if case == "position" else 1 if case == "duplicate_position" else 2)
        elif case.startswith("template_") or case == "duplicate_template_code":
            if case != "duplicate_template_code":
                template["code"] = "other"
            template.update({"template_range": {"max_difficulty": 0}, "template_budget": {"positive_effect_budget": -1}, "template_rarity": {"rarity": "unknown"}}.get(case, {}))
            statement = insert(CardTemplate).values(**template)
        elif case.startswith("effect_") or case == "duplicate_effect_code":
            if case != "duplicate_effect_code":
                effect["code"] = "other"
            field = case.removeprefix("effect_")
            effect.update({"type": {"type": "unknown"}, "trigger": {"trigger": "unknown"}, "rarity": {"rarity": "unknown"}, "sign": {"value": -1}, "cost": {"cost": 0}, "weight": {"weight": 0}}.get(field, {}))
            statement = insert(Effect).values(**effect)
        else:
            statement = insert(CardTemplateEffect).values(card_template_id=uuid4() if case == "missing_template" else tid, effect_id=uuid4() if case == "missing_effect" else eid)
        with pytest.raises(IntegrityError):
            async with connection.begin_nested():
                await connection.execute(statement)

    asyncio.run(in_schema(database_url, check))


def test_cascade_and_question_defaults(database_url):
    async def check(connection):
        qid = uuid4()
        await connection.execute(insert(Question).values(id=qid, text="Q", category="ddd", difficulty=5))
        row = (await connection.execute(select(Question.__table__).where(Question.id == qid))).mappings().one()
        assert row["is_active"] is True
        assert row["created_at"].tzinfo is not None
        for position in range(1, 5):
            await connection.execute(insert(AnswerOption).values(question_id=qid, text=str(position), is_correct=position == 1, position=position))
        await connection.execute(Question.__table__.delete().where(Question.id == qid))
        assert (await connection.execute(select(AnswerOption.id))).all() == []
    asyncio.run(in_schema(database_url, check))
