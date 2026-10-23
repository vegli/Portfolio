from collections.abc import AsyncIterator
from uuid import UUID

from app.application.errors import (
    ConcurrentUpdate, GameAlreadyFinished, InvalidGamePhase, SessionUnavailable,
)
from app.application.models import StoredSession
from app.application.ports import SessionRepository, SessionTokens
from app.domain.game_session import GamePhase, GameSession, GameStatus


async def load_authorized(
    sessions: SessionRepository, tokens: SessionTokens, session_id: UUID, token: str,
) -> StoredSession:
    stored = await sessions.get(session_id)
    if stored is None or not tokens.verify(token, stored.token_verifier):
        raise SessionUnavailable("Session unavailable")
    return stored


async def update_attempts(
    sessions: SessionRepository, tokens: SessionTokens, session_id: UUID, token: str,
) -> AsyncIterator[StoredSession]:
    for _ in range(3):
        yield await load_authorized(sessions, tokens, session_id, token)
    # A final failed CAS may mean the key expired, rather than contention.
    await load_authorized(sessions, tokens, session_id, token)
    raise ConcurrentUpdate("Session changed during all three update attempts")


def require_phase(session: GameSession, phase: GamePhase) -> None:
    if session.status is GameStatus.FINISHED:
        raise GameAlreadyFinished("Game has already finished")
    if session.status is not GameStatus.ACTIVE or session.phase is not phase:
        raise InvalidGamePhase("Action is not permitted in the current phase")
