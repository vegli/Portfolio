from collections.abc import Awaitable, Callable
from uuid import UUID

from redis.asyncio import Redis
from redis.backoff import NoBackoff
from redis.exceptions import ConnectionError, RedisError, TimeoutError, WatchError
from redis.asyncio.retry import Retry

from app.application.errors import CatalogFailure, PersistenceFailure
from app.application.models import ExpiryPolicy, StoredSession
from app.domain.card import CardTemplate
from app.domain.game_session import GameSession
from app.domain.question import Question
from app.persistence.session_codec import decode_snapshot, encode_snapshot


SESSION_TTL_SECONDS = 900


def create_redis_client(url: str) -> Redis:
    # Never retry an ambiguous write after a connection failure.
    return Redis.from_url(url, socket_connect_timeout=5, socket_timeout=5,
                          retry=Retry(NoBackoff(), 0), decode_responses=False)


class RedisSessionRepository:
    def __init__(
        self, client: Redis,
        load_card_content: Callable[[UUID, UUID], Awaitable[tuple[Question, CardTemplate]]],
    ) -> None:
        self.client = client
        self.load_card_content = load_card_content

    @staticmethod
    def key(session_id: UUID) -> str:
        if not isinstance(session_id, UUID):
            raise TypeError('session ID must be a UUID')
        return f'game:session:{session_id}'

    async def create(self, session: GameSession, *, token_verifier: bytes) -> None:
        data = encode_snapshot(session, 0, token_verifier)
        try:
            created = await self.client.set(self.key(session.id), data, nx=True, ex=SESSION_TTL_SECONDS)
            if not created:
                raise PersistenceFailure('Session already exists')
        except RedisError:
            raise PersistenceFailure('Unable to create session') from None

    async def get(self, session_id: UUID) -> StoredSession | None:
        try:
            data = await self.client.get(self.key(session_id))
            if data is None:
                return None
            snapshot = decode_snapshot(data, session_id)
            if snapshot.current_card is None:
                return snapshot.hydrate()
            question, template = await self.load_card_content(
                snapshot.current_card.question_id, snapshot.current_card.template_id,
            )
            return snapshot.hydrate(question, template)
        except (RedisError, CatalogFailure):
            raise PersistenceFailure('Unable to retrieve session') from None

    async def compare_and_swap(
        self, session: GameSession, *, expected_version: int, expiry: ExpiryPolicy,
    ) -> bool:
        if type(expected_version) is not int or expected_version < 0:
            raise ValueError('expected version must be a nonnegative integer')
        if not isinstance(expiry, ExpiryPolicy):
            raise TypeError('expiry must be an ExpiryPolicy')
        key = self.key(session.id)
        try:
            async with self.client.pipeline(transaction=True) as pipe:
                await pipe.watch(key)
                data = await pipe.get(key)
                if data is None:
                    return False
                stored = decode_snapshot(data, session.id)
                if stored.version != expected_version:
                    return False
                ttl = await pipe.pttl(key)
                if ttl == -2:
                    return False
                if ttl == -1:
                    raise PersistenceFailure('Session has no expiration')
                replacement = encode_snapshot(session, expected_version + 1, bytes.fromhex(stored.token_verifier))
                pipe.multi()
                if expiry is ExpiryPolicy.RENEW_ACTIVITY:
                    pipe.set(key, replacement, xx=True, ex=SESSION_TTL_SECONDS)
                else:
                    pipe.set(key, replacement, xx=True, keepttl=True)
                result = await pipe.execute()
                return bool(result[0])
        except WatchError as exc:
            # redis-py also wraps connection failures during WATCH as WatchError.
            if isinstance(exc.__cause__ or exc.__context__, (ConnectionError, TimeoutError, OSError)):
                raise PersistenceFailure("Unable to update session") from None
            return False
        except RedisError:
            raise PersistenceFailure('Unable to update session') from None
