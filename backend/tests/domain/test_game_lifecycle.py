from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.domain.card import CardRarity, CardTemplate, DrawnCard
from app.domain.effect import Effect, EffectTrigger, EffectType
from app.domain.game_session import AnswerResult, GameOverReason, GamePhase, GameSession, GameStatus
from app.domain.player import PlayerState
from app.domain.question import Question


@pytest.fixture
def card(question: Question) -> DrawnCard:
    effects = tuple(
        Effect(kind, value, trigger)
        for trigger, values in (
            (EffectTrigger.CORRECT, (10, 15, 3)),
            (EffectTrigger.INCORRECT, (-20, -30, -5)),
        )
        for kind, value in zip((EffectType.HP, EffectType.SCORE, EffectType.TIME), values)
    )
    return DrawnCard(uuid4(), CardTemplate(uuid4(), CardRarity.COMMON, 1, 5, 3, 3),
                     question, effects)


@pytest.fixture
def created() -> GameSession:
    return GameSession(uuid4(), datetime(2026, 10, 23, tzinfo=UTC))


@pytest.fixture
def active(created: GameSession, card: DrawnCard) -> GameSession:
    return created.activate(card, now=created.last_updated_at + timedelta(seconds=10))


def answer(session: GameSession, correct: bool = True, *, now: datetime | None = None) -> GameSession:
    card = session.current_card
    option = card.question.options[0 if correct else 1].id
    return session.submit_answer(card.id, option, now=session.last_updated_at if now is None else now)


def next_card(card: DrawnCard) -> DrawnCard:
    return replace(card, id=uuid4(), question=replace(card.question, id=uuid4()))


def test_activation_starts_timer_after_preparation(created: GameSession, card: DrawnCard) -> None:
    now = created.last_updated_at + timedelta(days=1)
    session = created.activate(card, now=now)
    assert session.status is GameStatus.ACTIVE
    assert session.phase is GamePhase.AWAITING_ANSWER
    assert session.player == PlayerState()
    assert session.remaining_time_ms == 60_000
    assert session.last_updated_at == now
    assert session.current_card is card
    assert session.used_question_ids == frozenset({card.question.id})
    assert session.last_answer_result is None
    assert created.status is GameStatus.CREATED
    assert not created.used_question_ids


@pytest.mark.parametrize("changes", [
    {"player": PlayerState(hp=90)}, {"player": PlayerState(score=1)},
    {"player": PlayerState(correct_streak=1)}, {"remaining_time_ms": 59_000},
    {"used_question_ids": frozenset({uuid4()})},
])
def test_activation_requires_fresh_state(created: GameSession, card: DrawnCard, changes: dict) -> None:
    with pytest.raises(ValueError):
        replace(created, **changes).activate(card, now=created.last_updated_at)


@pytest.mark.parametrize("correct,hp,score,streak,remaining", [
    (True, 110, 45, 3, 62_000), (False, 80, -30, 0, 54_000),
])
def test_answer_processing(
    active: GameSession, correct: bool, hp: int, score: int, streak: int, remaining: int,
) -> None:
    session = replace(active, player=PlayerState(correct_streak=2))
    updated = answer(session, correct, now=session.last_updated_at + timedelta(seconds=1))
    assert updated.player == PlayerState(hp, score, streak)
    assert updated.remaining_time_ms == remaining
    assert updated.phase is GamePhase.AWAITING_NEXT_CARD
    assert updated.status is GameStatus.ACTIVE
    result = updated.last_answer_result
    assert result.is_correct is correct
    assert result.score_delta == score
    assert result.correct_answer_id == session.current_card.question.correct_answer_id
    trigger = EffectTrigger.CORRECT if correct else EffectTrigger.INCORRECT
    assert result.applied_effects == tuple(e for e in session.current_card.effects if e.trigger is trigger)
    assert session.player == PlayerState(correct_streak=2)
    assert session.last_answer_result is None


def test_half_up_scoring_in_aggregate(active: GameSession) -> None:
    card = replace(active.current_card, question=replace(active.current_card.question, difficulty=2))
    session = replace(active, current_card=card, player=PlayerState(correct_streak=2))
    assert answer(session).player.score == 38


def test_result_retained_on_refresh_and_cleared_on_next_card(active: GameSession) -> None:
    evaluated = answer(active)
    refreshed = evaluated.refresh(now=evaluated.last_updated_at + timedelta(seconds=1))
    assert refreshed.last_answer_result is evaluated.last_answer_result
    card = next_card(active.current_card)
    updated = refreshed.assign_next_card(card, now=refreshed.last_updated_at + timedelta(seconds=1))
    assert updated.phase is GamePhase.AWAITING_ANSWER
    assert updated.current_card is card
    assert updated.last_answer_result is None
    assert updated.remaining_time_ms == evaluated.remaining_time_ms - 2000
    assert updated.used_question_ids == active.used_question_ids | {card.question.id}
    assert evaluated.last_answer_result is not None


def test_wrong_ids_and_duplicate_answer(active: GameSession) -> None:
    with pytest.raises(ValueError):
        active.submit_answer(uuid4(), active.current_card.question.options[0].id, now=active.last_updated_at)
    with pytest.raises(ValueError):
        active.submit_answer(active.current_card.id, uuid4(), now=active.last_updated_at)
    with pytest.raises(ValueError):
        answer(answer(active))


def test_invalid_transitions(created: GameSession, active: GameSession, card: DrawnCard) -> None:
    with pytest.raises(ValueError):
        created.submit_answer(card.id, card.question.options[0].id, now=created.last_updated_at)
    with pytest.raises(ValueError):
        created.assign_next_card(card, now=created.last_updated_at)
    with pytest.raises(ValueError):
        active.activate(card, now=active.last_updated_at)
    with pytest.raises(ValueError):
        active.assign_next_card(next_card(card), now=active.last_updated_at)


def test_repeated_question_rejected_even_with_new_card_id(active: GameSession) -> None:
    evaluated = answer(active)
    with pytest.raises(ValueError):
        evaluated.assign_next_card(replace(active.current_card, id=uuid4()), now=evaluated.last_updated_at)


@pytest.mark.parametrize("microseconds,expired,remaining", [
    (999, False, 1), (1000, True, 0), (1001, True, 0), (100_000, True, 0),
])
def test_expiry_boundary_blocks_rewards(active: GameSession, microseconds: int, expired: bool, remaining: int) -> None:
    session = replace(active, remaining_time_ms=1)
    updated = answer(session, now=session.last_updated_at + timedelta(microseconds=microseconds))
    if expired:
        assert updated.game_over_reason is GameOverReason.TIME_EXPIRED
        assert updated.player == session.player
        assert updated.last_answer_result is None
        assert updated.remaining_time_ms == remaining
    else:
        assert updated.player.score == 35
        assert updated.remaining_time_ms == remaining + 3000


def test_expiration_precedes_semantic_validation(active: GameSession) -> None:
    now = active.last_updated_at + timedelta(seconds=60)
    expired = active.submit_answer(uuid4(), uuid4(), now=now)
    assert expired.game_over_reason is GameOverReason.TIME_EXPIRED
    assert expired.last_answer_result is None
    assert active.assign_next_card(active.current_card, now=now).game_over_reason is GameOverReason.TIME_EXPIRED


def test_expiry_while_waiting_preserves_result_and_used_questions(active: GameSession) -> None:
    evaluated = answer(active)
    expired = evaluated.assign_next_card(next_card(active.current_card),
                                        now=evaluated.last_updated_at + timedelta(seconds=64))
    assert expired.status is GameStatus.FINISHED
    assert expired.phase is None
    assert expired.game_over_reason is GameOverReason.TIME_EXPIRED
    assert expired.last_answer_result is evaluated.last_answer_result
    assert expired.used_question_ids == evaluated.used_question_ids
    assert expired.current_card is evaluated.current_card


@pytest.mark.parametrize("hp,time_ms,reason", [
    (10, 4000, GameOverReason.HP_DEPLETED),
    (100, 4000, GameOverReason.TIME_EXPIRED),
    (10, 60_000, GameOverReason.HP_DEPLETED),
])
def test_post_answer_game_over_priority(active: GameSession, hp: int, time_ms: int, reason: GameOverReason) -> None:
    session = replace(active, player=PlayerState(hp=hp), remaining_time_ms=time_ms)
    updated = answer(session, False)
    assert updated.status is GameStatus.FINISHED
    assert updated.phase is None
    assert updated.game_over_reason is reason
    assert updated.player.score == -30
    assert updated.last_answer_result.is_correct is False
    assert updated.refresh(now=updated.last_updated_at + timedelta(days=1)) is updated


@pytest.mark.parametrize("hp,time_ms,reason", [
    (0, 0, GameOverReason.TIME_EXPIRED), (-1, 0, GameOverReason.TIME_EXPIRED),
    (0, 1000, GameOverReason.HP_DEPLETED),
])
def test_preexisting_depletion_prevents_evaluation(active: GameSession, hp: int, time_ms: int, reason: GameOverReason) -> None:
    session = replace(active, player=PlayerState(hp=hp), remaining_time_ms=time_ms)
    updated = answer(session)
    assert updated.game_over_reason is reason
    assert updated.player == session.player
    assert updated.last_answer_result is None


def test_finished_rejects_gameplay(active: GameSession) -> None:
    finished = active.refresh(now=active.last_updated_at + timedelta(seconds=60))
    with pytest.raises(ValueError):
        answer(finished)
    with pytest.raises(ValueError):
        finished.assign_next_card(next_card(active.current_card), now=finished.last_updated_at)
    with pytest.raises(ValueError):
        finished.activate(active.current_card, now=finished.last_updated_at)


def test_refresh_does_not_reset_or_pause_timer(active: GameSession, created: GameSession) -> None:
    assert created.refresh(now=created.last_updated_at + timedelta(days=1)) is created
    first = active.refresh(now=active.last_updated_at + timedelta(seconds=10))
    second = first.refresh(now=active.last_updated_at + timedelta(seconds=60))
    assert first.remaining_time_ms == 50_000
    assert second.remaining_time_ms == 0
    assert second.game_over_reason is GameOverReason.TIME_EXPIRED


def test_submillisecond_remainder_survives_refresh_answer_and_assignment(active: GameSession) -> None:
    origin = active.last_updated_at
    first = active.refresh(now=origin + timedelta(microseconds=600))
    assert first.last_updated_at == origin
    evaluated = answer(first, now=origin + timedelta(microseconds=1200))
    assert evaluated.last_updated_at == origin + timedelta(milliseconds=1)
    assigned = evaluated.assign_next_card(next_card(active.current_card), now=origin + timedelta(microseconds=1800))
    refreshed = assigned.refresh(now=origin + timedelta(microseconds=2400))
    assert refreshed.remaining_time_ms == 62_998
    assert refreshed.last_updated_at == origin + timedelta(milliseconds=2)


def test_timezone_equivalence_and_dst_elapsed_time(active: GameSession) -> None:
    offset = timezone(timedelta(hours=2))
    now = (active.last_updated_at + timedelta(seconds=1)).astimezone(offset)
    assert active.refresh(now=now).remaining_time_ms == 59_000
    zone = ZoneInfo("Europe/Budapest")
    before = datetime(2026, 10, 25, 2, 59, 59, tzinfo=zone, fold=0)
    after = datetime(2026, 10, 25, 2, 0, 0, tzinfo=zone, fold=1)
    assert replace(active, last_updated_at=before).refresh(now=after).remaining_time_ms == 59_000


@pytest.mark.parametrize("now,error", [(None, TypeError), (1, TypeError),
    (datetime(2026, 10, 23), ValueError), (datetime(2020, 1, 1, tzinfo=UTC), ValueError)])
def test_invalid_timestamps_on_all_operations(active: GameSession, now: object, error: type) -> None:
    for operation in (
        lambda: active.refresh(now=now),
        lambda: active.submit_answer(active.current_card.id, active.current_card.question.options[0].id, now=now),
        lambda: active.assign_next_card(active.current_card, now=now),
        lambda: active.activate(active.current_card, now=now),
    ):
        with pytest.raises(error):
            operation()


def test_basic_types_validated_before_expiration(active: GameSession) -> None:
    now = active.last_updated_at + timedelta(seconds=100)
    for card_id, option_id in ((None, uuid4()), (uuid4(), "option")):
        with pytest.raises(TypeError):
            active.submit_answer(card_id, option_id, now=now)
    with pytest.raises(TypeError):
        active.assign_next_card(None, now=now)
    with pytest.raises(TypeError):
        active.activate(None, now=now)


def test_result_is_immutable_and_copies_effects(active: GameSession) -> None:
    evaluated = answer(active)
    result: AnswerResult = evaluated.last_answer_result
    effects = list(result.applied_effects)
    copied = replace(result, applied_effects=effects)
    effects.clear()
    assert copied == result
    with pytest.raises(FrozenInstanceError):
        result.score_delta = 0
    with pytest.raises(FrozenInstanceError):
        evaluated.player.score = 0
    assert active.last_answer_result is None
    assert active.player == PlayerState()


@pytest.mark.parametrize("changes,error", [
    ({"card_id": "id"}, TypeError), ({"is_correct": 1}, TypeError),
    ({"score_delta": True}, TypeError), ({"applied_effects": (None,)}, TypeError),
    ({"is_correct": False}, ValueError),
    ({"applied_effects": (Effect(EffectType.HP, -10, EffectTrigger.INCORRECT),)}, ValueError),
])
def test_answer_result_validation(active: GameSession, changes: dict, error: type) -> None:
    with pytest.raises(error):
        replace(answer(active).last_answer_result, **changes)


def test_result_must_match_snapshot(active: GameSession, created: GameSession) -> None:
    evaluated = answer(active)
    result = evaluated.last_answer_result
    for session in (created, active):
        with pytest.raises(ValueError):
            replace(session, last_answer_result=result)
    with pytest.raises(TypeError):
        replace(evaluated, last_answer_result={})
    with pytest.raises(ValueError):
        replace(evaluated, last_answer_result=replace(result, card_id=uuid4()))
    with pytest.raises(ValueError):
        replace(evaluated, last_answer_result=replace(result, answer_option_id=uuid4(), is_correct=False,
                                                    applied_effects=()))


def test_rejected_action_cannot_avoid_elapsed_time(active: GameSession) -> None:
    with pytest.raises(ValueError):
        active.submit_answer(uuid4(), uuid4(), now=active.last_updated_at + timedelta(seconds=10))
    updated = answer(active, now=active.last_updated_at + timedelta(seconds=11))
    assert updated.remaining_time_ms == 52_000
    assert active.remaining_time_ms == 60_000


def test_older_question_cannot_be_reused(active: GameSession) -> None:
    evaluated = answer(active)
    assigned = evaluated.assign_next_card(next_card(active.current_card), now=evaluated.last_updated_at)
    evaluated_again = answer(assigned)
    assert len(evaluated_again.used_question_ids) == 2
    with pytest.raises(ValueError):
        evaluated_again.assign_next_card(active.current_card, now=evaluated_again.last_updated_at)


def test_answer_without_effects_and_empty_result_effects(created: GameSession, card: DrawnCard) -> None:
    card = replace(card, template=replace(card.template, positive_effect_budget=0, negative_effect_budget=0),
                   effects=())
    active = created.activate(card, now=created.last_updated_at)
    evaluated = answer(active, now=active.last_updated_at + timedelta(milliseconds=123))
    assert evaluated.player == PlayerState(hp=100, score=20, correct_streak=1)
    assert evaluated.remaining_time_ms == 59_877
    assert evaluated.last_answer_result.applied_effects == ()


@pytest.mark.parametrize("timestamp", [None, "now", 1])
def test_snapshot_timestamp_type(created: GameSession, timestamp: object) -> None:
    with pytest.raises(TypeError):
        replace(created, last_updated_at=timestamp)
