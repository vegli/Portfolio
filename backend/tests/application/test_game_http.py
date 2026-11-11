from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.games import GameServices, get_services
from app.application.errors import CatalogFailure, ConcurrentUpdate, NoPlayableQuestions, PersistenceFailure
from app.config import Settings
from app.main import create_app
from app.security.session_tokens import SecureSessionTokens


@pytest.fixture
def client(env):
    tokens = SecureSessionTokens()
    env.start.tokens = env.get.tokens = tokens
    app = create_app(Settings(debug=True))
    app.dependency_overrides[get_services] = lambda: GameServices(env.start, env.get)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_start_and_restore_safe_state(client, env):
    response = client.post('/api/v1/games')
    assert response.status_code == 201
    state = response.json()
    token, game_id = state['session_token'], state['game_id']
    assert response.headers['location'] == f'/api/v1/games/{game_id}'
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert 'correct_answer_id' not in response.text
    assert 'token_verifier' not in response.text
    assert state['player'] == {'hp': 100, 'score': 0, 'correct_streak': 0}
    assert state['remaining_time_ms'] == 60000
    assert len(state['card']['question']['options']) == 4
    deadline = next(iter(env.sessions.deadlines.values()))
    env.clock.advance(4)
    restored = client.get(response.headers['location'], headers={'X-Game-Token': token})
    assert restored.status_code == 200
    assert restored.json()['game_id'] == game_id
    assert restored.json()['remaining_time_ms'] == 56000
    assert 'session_token' not in restored.text and token not in restored.text
    assert 'correct_answer_id' not in restored.text
    assert next(iter(env.sessions.deadlines.values())) == deadline


def test_missing_invalid_unknown_and_expired_are_indistinguishable(client, env):
    game = client.post('/api/v1/games').json()
    url = f'/api/v1/games/{game["game_id"]}'
    responses = [client.get(url), client.get(url, headers={'X-Game-Token': 'x' * 43}),
                 client.get(f'/api/v1/games/{uuid4()}', headers={'X-Game-Token': game['session_token']})]
    env.clock.advance(900)
    responses.append(client.get(url, headers={'X-Game-Token': game['session_token']}))
    for response in responses:
        assert response.status_code == 404
        assert response.json() == {'error': {'code': 'SESSION_UNAVAILABLE', 'message': 'Session unavailable.'}}
        assert response.headers['cache-control'] == 'no-store'


def test_get_confirms_game_timer_expiration(client, env):
    game = client.post('/api/v1/games').json()
    deadline = next(iter(env.sessions.deadlines.values()))
    env.clock.advance(60)
    response = client.get(f'/api/v1/games/{game["game_id"]}', headers={'X-Game-Token': game['session_token']})
    assert response.status_code == 200
    assert response.json()['status'] == 'finished'
    assert response.json()['game_over_reason'] == 'time_expired'
    assert 'correct_answer_id' not in response.text
    assert next(iter(env.sessions.deadlines.values())) == deadline


@pytest.mark.parametrize('failure,status,code', [
    (CatalogFailure, 503, 'SERVICE_UNAVAILABLE'), (PersistenceFailure, 503, 'SERVICE_UNAVAILABLE'),
    (NoPlayableQuestions, 503, 'NO_PLAYABLE_QUESTIONS'), (ConcurrentUpdate, 409, 'CONCURRENT_UPDATE'),
    (RuntimeError, 500, 'INTERNAL_ERROR'),
])
def test_errors_are_sanitized_even_with_debug_enabled(client, env, failure, status, code):
    async def fail():
        raise failure('private credential and database details')
    env.start.execute = fail
    response = client.post('/api/v1/games')
    assert response.status_code == status
    assert response.json()['error']['code'] == code
    assert 'private' not in response.text
    assert response.headers['cache-control'] == 'no-store'


def test_validation_does_not_echo_input(client):
    response = client.get('/api/v1/games/not-a-uuid', headers={'X-Game-Token': 'sensitive-value'})
    assert response.status_code == 422
    assert response.json()['error']['code'] == 'INVALID_REQUEST'
    assert 'sensitive' not in response.text and 'not-a-uuid' not in response.text


def test_out_of_scope_routes_absent(client):
    game_id = uuid4()
    for suffix in ('answers', 'cards/next', 'restart', 'finish'):
        assert client.post(f'/api/v1/games/{game_id}/{suffix}').status_code == 404


@pytest.mark.parametrize('store', ['catalog', 'sessions'])
def test_storage_failure_through_start_use_case(client, env, store):
    async def fail(*args, **kwargs):
        if store == 'catalog':
            raise CatalogFailure('database credentials must stay private')
        raise PersistenceFailure('redis credentials must stay private')
    if store == 'catalog':
        env.start.catalogs.load = fail
    else:
        env.start.sessions.create = fail
    response = client.post('/api/v1/games')
    assert response.status_code == 503
    assert response.json()['error']['code'] == 'SERVICE_UNAVAILABLE'
    assert 'credentials' not in response.text
    assert 'session_token' not in response.text
