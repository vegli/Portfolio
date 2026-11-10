"""Small starter catalog; run with python -m app.persistence.seed after migrations."""
import asyncio
from uuid import UUID, uuid5

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.persistence.database import create_database_engine, create_session_factory
from app.persistence.models import AnswerOption, CardTemplate, CardTemplateEffect, Effect, Question


_NAMESPACE = UUID("cff95039-485c-4830-bcd3-bf1ee4c0619f")


def seed_id(name: str) -> UUID:
    return uuid5(_NAMESPACE, name)


QUESTIONS = (
    ("http", "networking", 1, "Which HTTP status means Too Many Requests?",
     ("200", "404", "429", "503"), 3),
    ("transaction", "databases", 2, "Which ACID property means all transaction changes succeed or none do?",
     ("Isolation", "Atomicity", "Durability", "Consistency"), 2),
    ("injection", "security", 3, "Which technique separates SQL statement structure from user-supplied values?",
     ("String concatenation", "Base64 encoding", "Client-side validation", "Parameterized queries"), 4),
    ("aggregate", "ddd", 4, "In DDD, what is an aggregate root responsible for?",
     ("Protecting invariants within its aggregate", "Owning every database table", "Rendering the UI", "Routing all HTTP requests"), 1),
    ("index", "performance", 5, "What is a common write-side trade-off of adding database indexes?",
     ("Writes no longer need transactions", "Writes require additional index maintenance", "All queries become constant time", "Rows can no longer be updated"), 2),
)

# A small subset of the provisional catalog in docs/DOMAIN.md.
EFFECT_LEVELS = (
    ("common", 1, 10, 15, 3),
    ("rare", 3, 25, 40, 7),
    ("epic", 5, 45, 80, 12),
)


async def seed_catalog(session: AsyncSession) -> None:
    """Insert missing seed rows; caller owns the transaction. Existing rows are preserved."""
    for code, category, difficulty, question, options, correct in QUESTIONS:
        question_id = seed_id(f"question:{code}")
        await session.execute(insert(Question).values(
            id=question_id, text=question, category=category, difficulty=difficulty,
        ).on_conflict_do_nothing(index_elements=["id"]))
        for position, option in enumerate(options, 1):
            await session.execute(insert(AnswerOption).values(
                id=seed_id(f"option:{code}:{position}"), question_id=question_id,
                text=option, is_correct=position == correct, position=position,
            ).on_conflict_do_nothing(index_elements=["id"]))
    for rarity, cost, hp, score, seconds in EFFECT_LEVELS:
        for kind, magnitude in (("hp", hp), ("score", score), ("time", seconds)):
            for trigger, sign in (("correct", 1), ("incorrect", -1)):
                code = f"starter_{rarity}_{kind}_{trigger}"
                await session.execute(insert(Effect).values(
                    id=seed_id(code), code=code, description=f"{sign * magnitude:+d} {kind}",
                    type=kind, value=sign * magnitude, trigger=trigger,
                    rarity=rarity, cost=cost, weight=70,
                ).on_conflict_do_nothing(index_elements=["id"]))
    for rarity, budget in (("common", 3), ("rare", 6), ("epic", 10)):
        code = f"starter_{rarity}"
        template_id = seed_id(code)
        await session.execute(insert(CardTemplate).values(
            id=template_id, code=code, name=f"Starter {rarity}", description="Starter interview card",
            rarity=rarity, min_difficulty=1, max_difficulty=5,
            positive_effect_budget=budget, negative_effect_budget=budget,
        ).on_conflict_do_nothing(index_elements=["id"]))
        eligible_rarities = ("rare", "epic") if rarity == "epic" else (rarity,)
        for effect_rarity in eligible_rarities:
            for kind in ("hp", "score", "time"):
                for trigger in ("correct", "incorrect"):
                    await session.execute(insert(CardTemplateEffect).values(
                        card_template_id=template_id,
                        effect_id=seed_id(f"starter_{effect_rarity}_{kind}_{trigger}"),
                    ).on_conflict_do_nothing(index_elements=["card_template_id", "effect_id"]))


async def main() -> None:
    engine = create_database_engine(Settings().database_url)
    try:
        async with create_session_factory(engine).begin() as session:
            await seed_catalog(session)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
