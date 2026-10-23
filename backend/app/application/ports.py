from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.application.models import ExpiryPolicy, GameCatalogs, IssuedToken, StoredSession
from app.domain.game_session import GameSession


class CatalogRepository(Protocol):
    async def load(self) -> GameCatalogs:
        """Load one coherent catalog; adapter failures raise CatalogFailure."""
        ...


class SessionRepository(Protocol):
    async def create(self, session: GameSession, *, token_verifier: bytes) -> None:
        """Insert only, with a 15-minute TTL; failures raise PersistenceFailure."""
        ...

    async def get(self, session_id: UUID) -> StoredSession | None:
        """Hydrate domain state without changing TTL; missing/expired returns None."""
        ...

    async def compare_and_swap(
        self, session: GameSession, *, expected_version: int, expiry: ExpiryPolicy,
    ) -> bool:
        """Atomically replace/version existing state, preserving its verifier.

        Return False for missing keys or version conflicts; never recreate a key.
        RENEW_ACTIVITY sets 15 minutes from commit; PRESERVE retains the deadline.
        Operational failures raise PersistenceFailure, not False.
        """
        ...


class Clock(Protocol):
    def now(self) -> datetime:
        """Return a timezone-aware server timestamp; regressions are errors."""
        ...


class SessionTokens(Protocol):
    def issue(self) -> IssuedToken:
        """Issue a cryptographically random token and its verifier; never log either."""
        ...

    def verify(self, token: str, verifier: bytes) -> bool:
        """Compare equivalent-length digests in constant time; never log tokens."""
        ...
