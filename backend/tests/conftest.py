from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.domain.card import CardRarity, CardTemplate, DrawnCard
from app.domain.effect import Effect, EffectTrigger, EffectType
from app.domain.game_session import GameSession
from app.domain.question import AnswerOption, Question, QuestionCategory


@pytest.fixture
def game_content():
    options = tuple(AnswerOption(uuid4(), f'Option {i}') for i in range(4))
    question = Question(uuid4(), 'Question?', QuestionCategory.DATABASES, 2, options, options[1].id)
    template = CardTemplate(uuid4(), CardRarity.COMMON, 1, 5, 1, 1)
    effects = (Effect(EffectType.HP, 10, EffectTrigger.CORRECT),
               Effect(EffectType.TIME, -3, EffectTrigger.INCORRECT))
    card = DrawnCard(uuid4(), template, question, effects)
    now = datetime(2026, 11, 11, tzinfo=UTC)
    created = GameSession(uuid4(), now)
    active = created.activate(card, now=now)
    answered = active.submit_answer(card.id, question.correct_answer_id, now=now)
    return SimpleNamespace(question=question, template=template, card=card, now=now,
                           created=created, active=active, answered=answered)
