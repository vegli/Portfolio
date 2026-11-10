import asyncio
import os
from datetime import UTC, datetime
from random import Random
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.application.start_game import StartGame
from app.application.submit_answer import SubmitAnswer
from app.domain.card_factory import CardFactory
from app.persistence.catalog import SQLAlchemyCatalogRepository
from app.persistence.redis_sessions import RedisSessionRepository, create_redis_client
from app.persistence.seed import seed_catalog
from app.security.session_tokens import SecureSessionTokens
from .support import in_schema


def test_real_postgres_and_redis_game_round_trip(database_url):
    url = os.environ.get('TEST_REDIS_URL')
    if not url:
        pytest.skip('Set TEST_REDIS_URL to run Redis/PostgreSQL integration')

    async def check(connection):
        factory = async_sessionmaker(connection, expire_on_commit=False)
        async with factory.begin() as session:
            await seed_catalog(session)
        catalogs = SQLAlchemyCatalogRepository(factory)
        client = create_redis_client(url)
        sessions = RedisSessionRepository(client, catalogs.load_card_content)
        clock = SimpleNamespace(now=lambda: datetime(2026, 11, 11, tzinfo=UTC))
        tokens = SecureSessionTokens()
        game_id = None
        try:
            game = await StartGame(sessions, catalogs, clock, tokens, lambda: CardFactory(Random(42))).execute()
            game_id = game.state.id
            loaded = await sessions.get(game_id)
            result = await SubmitAnswer(sessions, clock, tokens).execute(
                game_id, game.token, card_id=loaded.session.current_card.id,
                answer_option_id=loaded.session.current_card.question.correct_answer_id,
            )
            assert result.accepted
            reloaded = await sessions.get(game_id)
            assert reloaded.version == 1
            assert reloaded.session.last_answer_result.is_correct
            assert reloaded.session.player.score == result.state.player.score
        finally:
            if game_id is not None:
                await client.delete(sessions.key(game_id))
            await client.aclose()
    asyncio.run(in_schema(database_url, check))
