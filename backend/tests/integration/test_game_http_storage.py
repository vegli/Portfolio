import asyncio
import json
import os

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Settings
from app.main import create_app
from app.persistence.seed import seed_catalog
from .support import in_schema


def test_http_start_restore_with_real_stores(database_url):
    redis_url = os.environ.get('TEST_REDIS_URL')
    if not redis_url:
        pytest.skip('Set TEST_REDIS_URL for HTTP storage integration')

    async def check(connection):
        async with async_sessionmaker(connection).begin() as session:
            await seed_catalog(session)
        schema = await connection.scalar(text('SELECT current_schema()'))
        await connection.commit()
        url = connection.engine.url.update_query_dict({'options': f'-csearch_path={schema}'})
        app = create_app(Settings(database_url=url.render_as_string(hide_password=False), redis_url=redis_url))
        async with app.router.lifespan_context(app):
            sessions = app.state.games.get.sessions
            key = None
            try:
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                    started = await client.post('/api/v1/games')
                    assert started.status_code == 201
                    game = started.json()
                    key = f'game:session:{game["game_id"]}'
                    raw = await sessions.client.get(key)
                    assert raw is not None and game['session_token'].encode() not in raw
                    saved = json.loads(raw)
                    assert saved['current_card']['question_id'] == game['card']['question']['id']
                    assert 'correct_answer_id' not in started.text
                    assert len(game['card']['question']['options']) == 4
                    deadline = await sessions.client.pexpiretime(key)
                    restored = await client.get(started.headers['location'], headers={'X-Game-Token': game['session_token']})
                    assert restored.status_code == 200
                    assert restored.json()['card'] == game['card']
                    assert restored.json()['remaining_time_ms'] <= 60000
                    assert 'session_token' not in restored.text
                    assert await sessions.client.pexpiretime(key) == deadline
                    wrong = await client.get(started.headers['location'], headers={'X-Game-Token': 'x' * 43})
                    assert wrong.status_code == 404
                    await sessions.client.pexpireat(key, 1)
                    expired = await client.get(started.headers['location'], headers={'X-Game-Token': game['session_token']})
                    assert expired.status_code == 404 and expired.json() == wrong.json()
            finally:
                if key:
                    await sessions.client.delete(key)
        assert not hasattr(app.state, 'games')
    asyncio.run(in_schema(database_url, check))
