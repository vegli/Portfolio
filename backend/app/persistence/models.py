from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer,
    MetaData, SmallInteger, Text, UniqueConstraint, Uuid, func, text as sql_text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    })


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint("difficulty BETWEEN 1 AND 5", name="difficulty"),
        CheckConstraint("category IN ('backend_engineering', 'databases', 'networking', 'system_design', 'security', 'ddd', 'performance')", name="category"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    text: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[int] = mapped_column(SmallInteger)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=sql_text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AnswerOption(Base):
    __tablename__ = "answer_options"
    __table_args__ = (
        UniqueConstraint("question_id", "position"),
        CheckConstraint("position BETWEEN 1 AND 4", name="position"),
        Index("uq_answer_options_correct_question", "question_id", unique=True, postgresql_where=sql_text("is_correct")),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    question_id: Mapped[UUID] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    position: Mapped[int] = mapped_column(SmallInteger)


class CardTemplate(Base):
    __tablename__ = "card_templates"
    __table_args__ = (
        CheckConstraint("rarity IN ('common', 'rare', 'epic')", name="rarity"),
        CheckConstraint("min_difficulty BETWEEN 1 AND 5 AND max_difficulty BETWEEN min_difficulty AND 5", name="difficulty_range"),
        CheckConstraint("positive_effect_budget >= 0 AND negative_effect_budget >= 0", name="budgets"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    rarity: Mapped[str] = mapped_column(Text)
    min_difficulty: Mapped[int] = mapped_column(SmallInteger)
    max_difficulty: Mapped[int] = mapped_column(SmallInteger)
    positive_effect_budget: Mapped[int] = mapped_column(Integer)
    negative_effect_budget: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=sql_text("true"))


class Effect(Base):
    __tablename__ = "effects"
    __table_args__ = (
        CheckConstraint("type IN ('hp', 'score', 'time')", name="type"),
        CheckConstraint("trigger IN ('correct', 'incorrect')", name="trigger"),
        CheckConstraint("rarity IN ('common', 'rare', 'epic')", name="rarity"),
        CheckConstraint("cost > 0 AND weight > 0", name="cost_weight"),
        CheckConstraint("(trigger = 'correct' AND value > 0) OR (trigger = 'incorrect' AND value < 0)", name="trigger_value"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(Text, unique=True)
    description: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(Text)
    trigger: Mapped[str] = mapped_column(Text)
    value: Mapped[int] = mapped_column(Integer)
    rarity: Mapped[str] = mapped_column(Text)
    cost: Mapped[int] = mapped_column(Integer)
    weight: Mapped[int] = mapped_column(Integer)


class CardTemplateEffect(Base):
    __tablename__ = "card_template_effects"
    card_template_id: Mapped[UUID] = mapped_column(ForeignKey("card_templates.id", ondelete="CASCADE"), primary_key=True)
    effect_id: Mapped[UUID] = mapped_column(ForeignKey("effects.id", ondelete="CASCADE"), primary_key=True, index=True)
