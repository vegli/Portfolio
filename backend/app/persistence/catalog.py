from collections import defaultdict
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.errors import CatalogFailure
from app.application.models import GameCatalogs
from app.domain.card import CardRarity, CardTemplate
from app.domain.effect import EffectDefinition, EffectRarity, EffectTrigger, EffectType
from app.domain.question import AnswerOption, Question, QuestionCategory
from app.persistence import models


def _uuid(value: object) -> UUID:
    if not isinstance(value, UUID):
        raise ValueError("content identifiers must be UUID values")
    return value


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("question and option text must be nonempty strings")
    return value


def hydrate_question(row: models.Question, options: list[models.AnswerOption]) -> Question:
    if len(options) != 4 or [o.position for o in options] != [1, 2, 3, 4]:
        raise ValueError(f"question {row.id} must have exactly four ordered options")
    if any(o.question_id != row.id or type(o.is_correct) is not bool for o in options):
        raise ValueError(f"question {row.id} has invalid answer options")
    correct = [o for o in options if o.is_correct]
    if len(correct) != 1:
        raise ValueError(f"question {row.id} must have exactly one correct answer")
    return Question(
        _uuid(row.id), _text(row.text), QuestionCategory(row.category), row.difficulty,
        tuple(AnswerOption(_uuid(o.id), _text(o.text)) for o in options),
        _uuid(correct[0].id),
    )


class SQLAlchemyCatalogRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def load(self) -> GameCatalogs:
        try:
            async with self.sessions() as session, session.begin():
                # All queries must observe the same committed content snapshot.
                await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
                questions = (await session.scalars(
                    select(models.Question).where(models.Question.is_active).order_by(models.Question.id)
                )).all()
                options = (await session.scalars(
                    select(models.AnswerOption).join(models.Question)
                    .where(models.Question.is_active)
                    .order_by(models.AnswerOption.question_id, models.AnswerOption.position)
                )).all()
                templates = (await session.scalars(
                    select(models.CardTemplate).where(models.CardTemplate.is_active)
                    .order_by(models.CardTemplate.id)
                )).all()
                effects = (await session.scalars(
                    select(models.Effect).order_by(models.Effect.id)
                )).all()
                associations = (await session.scalars(
                    select(models.CardTemplateEffect).join(models.CardTemplate)
                    .where(models.CardTemplate.is_active)
                    .order_by(models.CardTemplateEffect.card_template_id, models.CardTemplateEffect.effect_id)
                )).all()
                by_question = defaultdict(list)
                for option in options:
                    by_question[option.question_id].append(option)
                effect_ids = {_uuid(effect.id) for effect in effects}
                allowed = {_uuid(template.id): set() for template in templates}
                for association in associations:
                    if association.card_template_id not in allowed or association.effect_id not in effect_ids:
                        raise ValueError("template association references missing content")
                    allowed[association.card_template_id].add(_uuid(association.effect_id))
                catalog = GameCatalogs(
                    tuple(hydrate_question(q, by_question[q.id]) for q in questions),
                    tuple(CardTemplate(
                        _uuid(t.id), CardRarity(t.rarity), t.min_difficulty, t.max_difficulty,
                        t.positive_effect_budget, t.negative_effect_budget,
                    ) for t in templates),
                    tuple(EffectDefinition(
                        _uuid(e.id), EffectType(e.type), e.value, EffectTrigger(e.trigger),
                        EffectRarity(e.rarity), e.cost, e.weight,
                    ) for e in effects),
                    {key: frozenset(values) for key, values in allowed.items()},
                )
                return catalog
        except (ValueError, TypeError) as exc:
            raise CatalogFailure(f"Invalid PostgreSQL catalog: {exc}") from exc
        except SQLAlchemyError as exc:
            raise CatalogFailure("Unable to load PostgreSQL catalog") from exc

    async def load_card_content(self, question_id: UUID, template_id: UUID) -> tuple[Question, CardTemplate]:
        """Load stable definitions referenced by a session, including inactive content."""
        try:
            async with self.sessions() as session, session.begin():
                await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
                question = await session.get(models.Question, question_id)
                template = await session.get(models.CardTemplate, template_id)
                if question is None or template is None:
                    raise ValueError('referenced card content is missing')
                options = (await session.scalars(
                    select(models.AnswerOption).where(models.AnswerOption.question_id == question_id)
                    .order_by(models.AnswerOption.position)
                )).all()
                return hydrate_question(question, list(options)), CardTemplate(
                    _uuid(template.id), CardRarity(template.rarity), template.min_difficulty,
                    template.max_difficulty, template.positive_effect_budget, template.negative_effect_budget,
                )
        except (ValueError, TypeError, SQLAlchemyError):
            raise CatalogFailure('Unable to hydrate referenced card content') from None
