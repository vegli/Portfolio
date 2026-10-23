from collections.abc import Callable
from uuid import UUID

from app.application.errors import CatalogFailure
from app.application.models import ExpiryPolicy, GameState
from app.application.ports import CatalogRepository, Clock, SessionRepository, SessionTokens
from app.application.session_access import require_phase, update_attempts
from app.domain.card_factory import CardFactory
from app.domain.game_session import GameOverReason, GamePhase, GameStatus


class NextCard:
    def __init__(
        self, sessions: SessionRepository, catalogs: CatalogRepository,
        clock: Clock, tokens: SessionTokens, card_factory: Callable[[], CardFactory],
    ) -> None:
        self.sessions, self.catalogs = sessions, catalogs
        self.clock, self.tokens, self.card_factory = clock, tokens, card_factory

    async def execute(self, session_id: UUID, token: str) -> GameState:
        factory = None
        async for stored in update_attempts(self.sessions, self.tokens, session_id, token):
            session = stored.session.refresh(now=self.clock.now())
            newly_finished = (stored.session.status is GameStatus.ACTIVE
                              and session.status is GameStatus.FINISHED)
            expiry = ExpiryPolicy.PRESERVE
            if not newly_finished:
                require_phase(session, GamePhase.AWAITING_NEXT_CARD)
                catalogs = await self.catalogs.load()
                if factory is None:
                    factory = self.card_factory()
                try:
                    card = factory.draw(
                        catalogs.questions, catalogs.templates, catalogs.effect_definitions,
                        session.used_question_ids,
                    )
                except ValueError as exc:
                    raise CatalogFailure("Invalid card catalog configuration") from exc
                now = self.clock.now()
                if card is None:
                    session = session.finish_no_questions_available(now=now)
                else:
                    session = session.assign_next_card(card, now=now)
                if (session.status is GameStatus.ACTIVE
                        or session.game_over_reason is GameOverReason.NO_QUESTIONS_AVAILABLE):
                    expiry = ExpiryPolicy.RENEW_ACTIVITY
            if await self.sessions.compare_and_swap(
                session, expected_version=stored.version, expiry=expiry,
            ):
                return GameState.from_session(session)
        raise AssertionError("update_attempts must raise after exhaustion")
