from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.card import CardRarity, CardTemplate, DrawnCard
from app.domain.game_session import GameSession, GameOverReason


def test_exhaustion_transition_is_constrained_and_preserves_feedback(question):
    now = datetime(2026, 10, 23, tzinfo=UTC)
    created = GameSession(uuid4(), now)
    card = DrawnCard(uuid4(), CardTemplate(uuid4(), CardRarity.COMMON, 1, 5, 0, 0), question, ())
    active = created.activate(card, now=now)
    answered = active.submit_answer(card.id, question.correct_answer_id, now=now)
    for invalid in (created, active):
        with pytest.raises(ValueError):
            invalid.finish_no_questions_available(now=now + timedelta(seconds=60))
    finished = answered.finish_no_questions_available(now=now + timedelta(seconds=1))
    assert finished.game_over_reason is GameOverReason.NO_QUESTIONS_AVAILABLE
    assert finished.last_answer_result is answered.last_answer_result
    assert finished.remaining_time_ms == 59_000
    assert answered.game_over_reason is None
    with pytest.raises(ValueError):
        finished.finish_no_questions_available(now=now + timedelta(seconds=2))
    expired = answered.finish_no_questions_available(now=now + timedelta(seconds=60))
    assert expired.game_over_reason is GameOverReason.TIME_EXPIRED
    with pytest.raises(ValueError):
        answered.finish_no_questions_available(now=now - timedelta(seconds=1))
    with pytest.raises(ValueError):
        answered.finish_no_questions_available(now=datetime(2026, 10, 23))
