import json
from datetime import timedelta
from uuid import uuid4

import pytest

from app.application.errors import PersistenceFailure
from app.persistence.session_codec import decode_snapshot, encode_snapshot


@pytest.mark.parametrize('state', ['created', 'active', 'answered', 'finished'])
def test_complete_round_trip(game_content, state):
    session = (game_content.answered.refresh(now=game_content.now + timedelta(seconds=60))
               if state == 'finished' else getattr(game_content, state))
    data = encode_snapshot(session, 3, b'x' * 32)
    stored = decode_snapshot(data, session.id).hydrate(game_content.question, game_content.template)
    assert stored.session == session
    assert stored.version == 3
    assert stored.token_verifier == b'x' * 32
    assert 'Question?' not in data
    assert 'Option ' not in data
    assert stored.session.status is session.status
    assert stored.session.last_updated_at.tzinfo is not None


@pytest.mark.parametrize('field,value', [
    ('schema_version', 2), ('schema_version', True), ('schema_version', '1'), ('version', -1), ('version', True), ('version', '1'),
    ('id', 'bad'), ('status', 'unknown'), ('remaining_time_ms', -1),
    ('remaining_time_ms', True), ('last_updated_at', '2026-11-11T00:00:00'),
    ('token_verifier', 'secret'), ('used_question_ids', ['bad']),
    ('phase', 'awaiting_next_card'), ('extra', 'unexpected'),
])
def test_invalid_snapshot(game_content, field, value):
    data = json.loads(encode_snapshot(game_content.active, 0, b'x' * 32))
    data[field] = value
    with pytest.raises(PersistenceFailure):
        decode_snapshot(json.dumps(data), game_content.active.id)


@pytest.mark.parametrize('data', [b'bad json', b'\xff', '{}', '[]', 'null'])
def test_malformed_snapshot(game_content, data):
    with pytest.raises(PersistenceFailure):
        decode_snapshot(data, game_content.active.id)


def test_missing_content_and_mismatched_ids(game_content):
    data = encode_snapshot(game_content.active, 0, b'x' * 32)
    with pytest.raises(PersistenceFailure):
        decode_snapshot(data, uuid4())
    with pytest.raises(PersistenceFailure):
        decode_snapshot(data, game_content.active.id).hydrate()


def test_invalid_feedback_and_effects(game_content):
    original = json.loads(encode_snapshot(game_content.answered, 1, b'x' * 32))
    original['last_answer_result']['correct_answer_id'] = str(uuid4())
    with pytest.raises(PersistenceFailure):
        decode_snapshot(json.dumps(original), game_content.active.id)
    original = json.loads(encode_snapshot(game_content.active, 0, b'x' * 32))
    original['current_card']['effects'][0]['value'] = -10
    with pytest.raises(PersistenceFailure):
        decode_snapshot(json.dumps(original), game_content.active.id)


def test_feedback_must_match_card(game_content):
    data = json.loads(encode_snapshot(game_content.answered, 1, b'x' * 32))
    data['last_answer_result']['applied_effects'][0]['value'] = 20
    snapshot = decode_snapshot(json.dumps(data), game_content.active.id)
    with pytest.raises(PersistenceFailure):
        snapshot.hydrate(game_content.question, game_content.template)
