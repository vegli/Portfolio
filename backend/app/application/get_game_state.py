from uuid import UUID

from app.application.models import ExpiryPolicy, GameState
from app.application.ports import Clock, SessionRepository, SessionTokens
from app.application.session_access import update_attempts
from app.domain.game_session import GameStatus


class GetGameState:
    def __init__(self, sessions: SessionRepository, clock: Clock, tokens: SessionTokens) -> None:
        self.sessions, self.clock, self.tokens = sessions, clock, tokens

    async def execute(self, session_id: UUID, token: str) -> GameState:
        async for stored in update_attempts(self.sessions, self.tokens, session_id, token):
            session = stored.session.refresh(now=self.clock.now())
            if (stored.session.status is not GameStatus.ACTIVE
                    or session.status is not GameStatus.FINISHED):
                return GameState.from_session(session)
            if await self.sessions.compare_and_swap(
                session, expected_version=stored.version, expiry=ExpiryPolicy.PRESERVE,
            ):
                return GameState.from_session(session)
        raise AssertionError("update_attempts must raise after exhaustion")
