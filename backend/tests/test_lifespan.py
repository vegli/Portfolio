from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

import app.main as main


def test_resources_created_in_lifespan_and_closed(monkeypatch):
    engine, redis = SimpleNamespace(dispose=AsyncMock()), SimpleNamespace(aclose=AsyncMock())
    constructed = []

    def database(url):
        constructed.append('database')
        return engine

    def cache(url):
        constructed.append('redis')
        return redis

    monkeypatch.setattr(main, 'create_database_engine', database)
    monkeypatch.setattr(main, 'create_redis_client', cache)
    monkeypatch.setattr(main, 'create_session_factory', lambda engine: None)
    app = main.create_app()
    assert constructed == []
    with TestClient(app) as client:
        assert constructed == ['database', 'redis']
        assert client.get('/health').status_code == 200
        assert hasattr(app.state, 'games')
    engine.dispose.assert_awaited_once()
    redis.aclose.assert_awaited_once()
    assert not hasattr(app.state, 'games')
