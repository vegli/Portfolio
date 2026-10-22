from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.card import CardRarity, CardTemplate, DrawnCard
from app.domain.game_session import GameOverReason, GamePhase, GameSession, GameStatus
from app.domain.player import PlayerState
from app.domain.question import Question


@pytest.fixture
def session() -> GameSession:
    return GameSession(id=uuid4(), last_updated_at=datetime(2026, 10, 22, tzinfo=UTC))


@pytest.fixture
def active(session: GameSession, question: Question) -> GameSession:
    template = CardTemplate(uuid4(), CardRarity.COMMON, 1, 5, 0, 0)
    card = DrawnCard(uuid4(), template, question, ())
    return replace(session, status=GameStatus.ACTIVE, phase=GamePhase.AWAITING_ANSWER,
                   current_card=card, used_question_ids=frozenset({question.id}))


def test_new_session_defaults(session: GameSession) -> None:
    assert session.status is GameStatus.CREATED
    assert session.phase is GamePhase.AWAITING_CARD
    assert session.player == PlayerState()
    assert session.remaining_time_ms == 60_000
    assert session.current_card is None
    assert session.used_question_ids == frozenset()
    assert session.game_over_reason is None


@pytest.mark.parametrize("remaining", [0, 90_000])
def test_time_has_no_upper_cap(session: GameSession, remaining: int) -> None:
    assert replace(session, remaining_time_ms=remaining).remaining_time_ms == remaining


@pytest.mark.parametrize("remaining", [True, 1.5, "60000"])
def test_integer_time(session: GameSession, remaining: object) -> None:
    with pytest.raises(TypeError):
        replace(session, remaining_time_ms=remaining)


def test_negative_time(session: GameSession) -> None:
    with pytest.raises(ValueError):
        replace(session, remaining_time_ms=-1)


def test_aware_timestamp(session: GameSession) -> None:
    with pytest.raises(ValueError):
        replace(session, last_updated_at=datetime(2026, 10, 22))
    timestamp = datetime(2026, 10, 22, tzinfo=timezone(timedelta(hours=2)))
    assert replace(session, last_updated_at=timestamp).last_updated_at == timestamp


@pytest.mark.parametrize("phase", [GamePhase.AWAITING_ANSWER, GamePhase.AWAITING_NEXT_CARD])
def test_active_phases(active: GameSession, phase: GamePhase) -> None:
    assert replace(active, phase=phase).phase is phase


@pytest.mark.parametrize("changes", [
    {"phase": None}, {"phase": GamePhase.AWAITING_CARD}, {"current_card": None},
    {"used_question_ids": frozenset()}, {"game_over_reason": GameOverReason.TIME_EXPIRED},
])
def test_active_structure(active: GameSession, changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        replace(active, **changes)


def test_created_structure(session: GameSession, active: GameSession) -> None:
    with pytest.raises(ValueError):
        replace(session, phase=GamePhase.AWAITING_ANSWER)
    with pytest.raises(ValueError):
        replace(active, status=GameStatus.CREATED, phase=GamePhase.AWAITING_CARD)


@pytest.mark.parametrize("reason", list(GameOverReason))
def test_finished_structure(active: GameSession, reason: GameOverReason) -> None:
    finished = replace(active, status=GameStatus.FINISHED, phase=None, game_over_reason=reason)
    assert finished.current_card == active.current_card
    assert finished.game_over_reason is reason
    with pytest.raises(ValueError):
        replace(finished, phase=GamePhase.AWAITING_NEXT_CARD)
    with pytest.raises(ValueError):
        replace(finished, game_over_reason=None)


@pytest.mark.parametrize("field,value", [("status", "active"), ("phase", "awaiting_answer"),
                                         ("game_over_reason", "time_expired")])
def test_enum_types(session: GameSession, field: str, value: str) -> None:
    with pytest.raises(TypeError):
        replace(session, **{field: value})


def test_immutable_session_and_used_ids(active: GameSession) -> None:
    used = set(active.used_question_ids)
    copied = replace(active, used_question_ids=used)
    used.clear()
    assert copied.used_question_ids == active.used_question_ids
    with pytest.raises(FrozenInstanceError):
        active.phase = GamePhase.AWAITING_NEXT_CARD
    with pytest.raises(FrozenInstanceError):
        active.player.hp = 0


def test_sessions_do_not_share_state(session: GameSession) -> None:
    other = GameSession(uuid4(), session.last_updated_at)
    changed = replace(session, player=PlayerState(hp=-10, score=-50))
    assert other.player == PlayerState()
    assert session.player == PlayerState()
    assert changed.player.hp == -10
