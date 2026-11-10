import asyncio
from random import Random
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, insert, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.application.errors import CatalogFailure
from app.domain.card_factory import CardFactory
from app.domain.effect import EffectRarity
from app.persistence.catalog import SQLAlchemyCatalogRepository
from app.persistence.models import AnswerOption, CardTemplate, CardTemplateEffect, Effect, Question
from app.persistence.seed import seed_catalog, seed_id
from .support import in_schema


def repository(connection):
    return SQLAlchemyCatalogRepository(async_sessionmaker(connection, expire_on_commit=False))


async def seed(connection):
    async with async_sessionmaker(connection).begin() as session:
        await seed_catalog(session)


def test_seed_twice_and_hydrate(database_url):
    async def check(connection):
        await seed(connection)
        first = await repository(connection).load()
        await seed(connection)
        second = await repository(connection).load()
        assert first == second
        for model, count in ((Question, 5), (AnswerOption, 20), (CardTemplate, 3), (Effect, 18), (CardTemplateEffect, 24)):
            assert await connection.scalar(select(func.count()).select_from(model)) == count
        assert len(first.questions) == 5
        assert {q.difficulty for q in first.questions} == {1, 2, 3, 4, 5}
        for question in first.questions:
            assert len(question.options) == 4
            assert question.correct_answer_id in {option.id for option in question.options}
        http = next(q for q in first.questions if q.id == seed_id('question:http'))
        assert [o.text for o in http.options] == ['200', '404', '429', '503']
        assert http.correct_answer_id == seed_id('option:http:3')
        assert {e.rarity for e in first.effect_definitions} == set(EffectRarity)
    asyncio.run(in_schema(database_url, check))


def test_seed_preserves_existing_content(database_url):
    async def check(connection):
        await seed(connection)
        await connection.execute(update(Question).where(Question.id == seed_id('question:http')).values(text='Edited question', is_active=False))
        unrelated = uuid4()
        await connection.execute(insert(Question).values(id=unrelated, text='Draft', category='ddd', difficulty=1, is_active=False))
        await connection.commit()
        await seed(connection)
        row = (await connection.execute(select(Question.__table__).where(Question.id == seed_id('question:http')))).mappings().one()
        assert row['text'] == 'Edited question'
        assert row['is_active'] is False
        assert await connection.scalar(select(Question.id).where(Question.id == unrelated)) == unrelated
    asyncio.run(in_schema(database_url, check))


@pytest.mark.parametrize('case', ['no_options', 'three_options', 'no_correct', 'blank_question', 'blank_option', 'two_correct'])
def test_invalid_question_fails_explicitly(database_url, case):
    async def check(connection):
        await seed(connection)
        qid = seed_id('question:http')
        if case in {'no_options', 'three_options'}:
            statement = delete(AnswerOption).where(AnswerOption.question_id == qid)
            if case == 'three_options':
                statement = statement.where(AnswerOption.position == 4)
            await connection.execute(statement)
        elif case == 'no_correct':
            await connection.execute(update(AnswerOption).where(AnswerOption.question_id == qid).values(is_correct=False))
        elif case == 'two_correct':
            await connection.execute(text('DROP INDEX uq_answer_options_correct_question'))
            await connection.execute(update(AnswerOption).where(AnswerOption.question_id == qid, AnswerOption.position == 1).values(is_correct=True))
        elif case == 'blank_question':
            await connection.execute(update(Question).where(Question.id == qid).values(text=' '))
        else:
            await connection.execute(update(AnswerOption).where(AnswerOption.question_id == qid).values(text=''))
        await connection.commit()
        with pytest.raises(CatalogFailure, match='Invalid PostgreSQL catalog'):
            await repository(connection).load()
    asyncio.run(in_schema(database_url, check))


def test_inactive_content_excluded_even_when_incomplete(database_url):
    async def check(connection):
        await seed(connection)
        qid, tid = seed_id('question:http'), seed_id('starter_common')
        await connection.execute(update(Question).where(Question.id == qid).values(is_active=False))
        await connection.execute(delete(AnswerOption).where(AnswerOption.question_id == qid))
        await connection.execute(update(CardTemplate).where(CardTemplate.id == tid).values(is_active=False))
        await connection.commit()
        catalog = await repository(connection).load()
        assert qid not in {q.id for q in catalog.questions}
        assert tid not in {t.id for t in catalog.templates}
        assert tid not in catalog.template_effect_ids
        assert len(catalog.questions) == 4
        assert len(catalog.templates) == 2
    asyncio.run(in_schema(database_url, check))


def test_generation_respects_associations_and_budgets(database_url):
    async def check(connection):
        await seed(connection)
        # Same-rarity, budget-fitting effects remain in the global catalog but are not associated.
        await connection.execute(delete(CardTemplateEffect).where(CardTemplateEffect.effect_id.in_([
            seed_id('starter_common_hp_correct'), seed_id('starter_common_hp_incorrect'),
        ])))
        await connection.commit()
        catalog = await repository(connection).load()
        factory = CardFactory(Random(42))
        seen = set()
        for _ in range(100):
            card = factory.draw(catalog.questions, catalog.templates, catalog.effect_definitions, set(),
                                template_effect_ids=catalog.template_effect_ids)
            seen.add(card.template.id)
            allowed = [e for e in catalog.effect_definitions if e.id in catalog.template_effect_ids[card.template.id]]
            for trigger, budget in [('correct', card.template.positive_effect_budget), ('incorrect', card.template.negative_effect_budget)]:
                rolled = [e for e in card.effects if e.trigger.value == trigger]
                assert rolled
                assert len({e.type for e in rolled}) == len(rolled)
                matched = [next(d for d in allowed if (d.type, d.trigger, d.value) == (e.type, e.trigger, e.value)) for e in rolled]
                assert sum(e.cost for e in matched) <= budget
            assert card.template.supports_difficulty(card.question.difficulty)
        assert seen == {t.id for t in catalog.templates}
    asyncio.run(in_schema(database_url, check))


def test_missing_associations_do_not_fall_back_to_global_effects(database_url):
    async def check(connection):
        await seed(connection)
        await connection.execute(delete(CardTemplateEffect))
        await connection.commit()
        catalog = await repository(connection).load()
        with pytest.raises(ValueError, match='no feasible'):
            CardFactory(Random(0)).draw(catalog.questions, catalog.templates, catalog.effect_definitions, set(),
                                       template_effect_ids=catalog.template_effect_ids)
    asyncio.run(in_schema(database_url, check))


def test_broken_effect_reference_fails_explicitly(database_url):
    async def check(connection):
        await seed(connection)
        # Simulate legacy/corrupt content despite the normal FK protection.
        await connection.execute(text('ALTER TABLE card_template_effects DROP CONSTRAINT fk_card_template_effects_effect_id_effects'))
        await connection.execute(update(CardTemplateEffect).where(
            CardTemplateEffect.card_template_id == seed_id('starter_common'),
            CardTemplateEffect.effect_id == seed_id('starter_common_hp_correct'),
        ).values(effect_id=uuid4()))
        await connection.commit()
        with pytest.raises(CatalogFailure, match='references missing content'):
            await repository(connection).load()
    asyncio.run(in_schema(database_url, check))


def test_empty_catalog(database_url):
    async def check(connection):
        catalog = await repository(connection).load()
        assert catalog.questions == catalog.templates == catalog.effect_definitions == ()
        assert dict(catalog.template_effect_ids) == {}
    asyncio.run(in_schema(database_url, check))


def test_database_failure_is_catalog_failure(database_url):
    async def check(connection):
        await connection.execute(text('DROP TABLE card_template_effects'))
        await connection.commit()
        with pytest.raises(CatalogFailure, match='Unable to load'):
            await repository(connection).load()
    asyncio.run(in_schema(database_url, check))


def test_seed_conflict_rolls_back_all_inserts(database_url):
    async def check(connection):
        await connection.execute(insert(Effect).values(
            id=uuid4(), code='starter_common_hp_correct', description='Existing content',
            type='hp', value=10, trigger='correct', rarity='common', cost=1, weight=70,
        ))
        await connection.commit()
        with pytest.raises(IntegrityError):
            await seed(connection)
        assert await connection.scalar(select(func.count()).select_from(Question)) == 0
        assert await connection.scalar(select(func.count()).select_from(AnswerOption)) == 0
        assert await connection.scalar(select(func.count()).select_from(Effect)) == 1
    asyncio.run(in_schema(database_url, check))


def test_session_content_lookup_includes_inactive_definitions(database_url):
    async def check(connection):
        await seed(connection)
        qid, tid = seed_id('question:http'), seed_id('starter_common')
        before = await repository(connection).load_card_content(qid, tid)
        await connection.execute(update(Question).where(Question.id == qid).values(is_active=False))
        await connection.execute(update(CardTemplate).where(CardTemplate.id == tid).values(is_active=False))
        await connection.commit()
        assert await repository(connection).load_card_content(qid, tid) == before
        with pytest.raises(CatalogFailure, match='referenced card content'):
            await repository(connection).load_card_content(uuid4(), tid)
    asyncio.run(in_schema(database_url, check))
