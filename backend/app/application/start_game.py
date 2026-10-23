from collections.abc import Callable
from uuid import uuid4

from app.application.errors import CatalogFailure, NoPlayableQuestions
from app.application.models import GameState, StartedGame
from app.application.ports import CatalogRepository, Clock, SessionRepository, SessionTokens
from app.domain.card_factory import CardFactory
from app.domain.game_session import GameSession


class StartGame:
    def __init__(
        self, sessions: SessionRepository, catalogs: CatalogRepository,
        clock: Clock, tokens: SessionTokens, card_factory: Callable[[], CardFactory],
    ) -> None:
        self.sessions, self.catalogs = sessions, catalogs
        self.clock, self.tokens, self.card_factory = clock, tokens, card_factory

    async def execute(self) -> StartedGame:
        session = GameSession(uuid4(), self.clock.now())
        catalogs = await self.catalogs.load()
        try:
            card = self.card_factory().draw(
                catalogs.questions, catalogs.templates, catalogs.effect_definitions,
                session.used_question_ids,
            )
        except ValueError as exc:
            raise CatalogFailure("Invalid card catalog configuration") from exc
        if card is None:
            raise NoPlayableQuestions("No playable question is available")
        session = session.activate(card, now=self.clock.now())
        issued = self.tokens.issue()
        await self.sessions.create(session, token_verifier=issued.verifier)
        return StartedGame(GameState.from_session(session), issued.token)
