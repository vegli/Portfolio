import asyncio
from random import Random
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.get_game_state import GetGameState
from app.application.models import GameCatalogs
from app.application.next_card import NextCard
from app.application.start_game import StartGame
from app.application.submit_answer import SubmitAnswer
from app.domain.card import CardRarity, CardTemplate
from app.domain.card_factory import CardFactory
from app.domain.question import AnswerOption, Question, QuestionCategory
from .fakes import FakeCatalogs, FakeClock, FakeSessions, FakeTokens


def run(awaitable):
    return asyncio.run(awaitable)


@pytest.fixture
def env():
    clock = FakeClock()
    sessions = FakeSessions(clock)
    tokens = FakeTokens()
    questions = []
    for i in range(4):
        options = tuple(AnswerOption(uuid4(), str(j)) for j in range(4))
        questions.append(Question(uuid4(), f'Question {i}', QuestionCategory.DATABASES,
                                  2, options, options[0].id))
    template = CardTemplate(uuid4(), CardRarity.COMMON, 1, 5, 0, 0)
    catalogs = FakeCatalogs(GameCatalogs(tuple(questions), (template,), ()))
    factories = []

    def provider():
        factory = CardFactory(Random(42))
        factories.append(factory)
        return factory

    return SimpleNamespace(
        clock=clock, sessions=sessions, tokens=tokens, catalogs=catalogs,
        factories=factories, provider=provider,
        start=StartGame(sessions, catalogs, clock, tokens, provider),
        submit=SubmitAnswer(sessions, clock, tokens),
        next=NextCard(sessions, catalogs, clock, tokens, provider),
        get=GetGameState(sessions, clock, tokens),
    )


def start(env):
    return run(env.start.execute())


def submit(env, game, *, correct=True):
    card = env.sessions.records[game.state.id].session.current_card
    option = card.question.options[0 if correct else 1].id
    return env.submit.execute(game.state.id, game.token, card_id=card.id, answer_option_id=option)


def answered(env):
    game = start(env)
    run(submit(env, game))
    return game
