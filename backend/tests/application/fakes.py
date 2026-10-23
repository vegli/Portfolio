from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from hmac import compare_digest

from app.application.errors import PersistenceFailure
from app.application.models import ExpiryPolicy, IssuedToken, StoredSession


class FakeClock:
    def __init__(self):
        self.time = datetime(2026, 10, 23, tzinfo=UTC)

    def now(self):
        return self.time

    def advance(self, seconds):
        self.time += timedelta(seconds=seconds)


class FakeTokens:
    """Predictable test credentials; not a production token implementation."""

    def __init__(self):
        self.count = 0
        self.checks = 0

    def issue(self):
        self.count += 1
        token = f'test-secret-{self.count}'
        return IssuedToken(token, sha256(token.encode()).digest())

    def verify(self, token, verifier):
        self.checks += 1
        return compare_digest(sha256(token.encode()).digest(), verifier)


class FakeCatalogs:
    def __init__(self, catalogs):
        self.catalogs = catalogs
        self.loads = 0
        self.on_load = None

    async def load(self):
        self.loads += 1
        if self.on_load:
            self.on_load()
        return self.catalogs


class FakeSessions:
    def __init__(self, clock):
        self.clock = clock
        self.records = {}
        self.deadlines = {}
        self.writes = []
        self.attempts = 0
        self.before_cas = None

    async def create(self, session, *, token_verifier):
        if session.id in self.records:
            raise PersistenceFailure('Session already exists')
        self.records[session.id] = StoredSession(session, 0, token_verifier)
        self.deadlines[session.id] = self.clock.now() + timedelta(minutes=15)

    async def get(self, session_id):
        if session_id in self.records and self.deadlines[session_id] <= self.clock.now():
            self.records.pop(session_id)
            self.deadlines.pop(session_id)
        return self.records.get(session_id)

    async def compare_and_swap(self, session, *, expected_version, expiry):
        self.attempts += 1
        if self.before_cas:
            callback = self.before_cas
            self.before_cas = None
            await callback(session)
        stored = await self.get(session.id)
        if stored is None or stored.version != expected_version:
            return False
        self.records[session.id] = replace(stored, session=session, version=stored.version + 1)
        if expiry is ExpiryPolicy.RENEW_ACTIVITY:
            self.deadlines[session.id] = self.clock.now() + timedelta(minutes=15)
        self.writes.append((session, expiry))
        return True
