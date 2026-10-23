from datetime import UTC, datetime, timedelta
from random import Random
from uuid import UUID, uuid4

import pytest

from app.domain.card import CardRarity, CardTemplate, DrawnCard
from app.domain.card_factory import CardFactory
from app.domain.effect import EffectDefinition, EffectRarity, EffectTrigger, EffectType
from app.domain.game_session import GameOverReason, GamePhase, GameSession, GameStatus
from app.domain.player import PlayerState
from app.domain.question import AnswerOption, Question, QuestionCategory


START = datetime(2026, 10, 23, tzinfo=UTC)


@pytest.fixture
def questions() -> tuple[Question, ...]:
    content = (
        ("Which HTTP status indicates rate limiting?", ("429", "200", "401", "404")),
        ("Which structure commonly backs a database index?", ("B-tree", "Stack", "Queue", "Heap")),
        ("Which protocol provides reliable ordered delivery?", ("TCP", "UDP", "IP", "ICMP")),
        ("Which HTTP method is defined as idempotent?", ("PUT", "POST", "CONNECT", "PATCH")),
        ("Which property makes committed transactions durable?", ("Durability", "Isolation", "Atomicity", "Consistency")),
        ("Which attack uses untrusted SQL input?", ("SQL injection", "CSRF", "DDoS", "Clickjacking")),
        ("Which operation usually has O(1) average lookup?", ("Hash lookup", "Linear search", "Sorting", "Tree traversal")),
    )
    result = []
    for index, (text, answers) in enumerate(content, start=1):
        options = tuple(AnswerOption(UUID(int=index * 10 + n), answer)
                        for n, answer in enumerate(answers))
        result.append(Question(UUID(int=index), text, QuestionCategory.BACKEND_ENGINEERING,
                               2, options, options[0].id))
    return tuple(result)


@pytest.fixture
def template() -> CardTemplate:
    return CardTemplate(UUID(int=100), CardRarity.COMMON, 2, 2, 3, 3)


@pytest.fixture
def effects() -> tuple[EffectDefinition, ...]:
    return tuple(
        EffectDefinition(UUID(int=200 + outcome * 10 + index), kind, value,
                         trigger, EffectRarity.COMMON, 1, 1)
        for outcome, (trigger, values) in enumerate((
            (EffectTrigger.CORRECT, (10, 15, 3)),
            (EffectTrigger.INCORRECT, (-20, -30, -5)),
        ))
        for index, (kind, value) in enumerate(zip(
            (EffectType.HP, EffectType.SCORE, EffectType.TIME), values,
        ))
    )


def draw(factory, questions, template, effects, session) -> DrawnCard:
    card = factory.draw(questions, (template,), effects, session.used_question_ids)
    assert card is not None
    assert card.question.id not in session.used_question_ids
    return card


def submit(session: GameSession, correct: bool, now: datetime) -> GameSession:
    card = session.current_card
    assert card is not None
    option_id = card.question.correct_answer_id if correct else next(
        option.id for option in card.question.options
        if option.id != card.question.correct_answer_id
    )
    return session.submit_answer(card.id, option_id, now=now)


def assert_finished_rejects_gameplay(session: GameSession, card: DrawnCard, now: datetime) -> None:
    with pytest.raises(ValueError):
        submit(session, True, now)
    with pytest.raises(ValueError):
        session.assign_next_card(card, now=now)
    with pytest.raises(ValueError):
        session.activate(card, now=now)
    assert session.refresh(now=now + timedelta(days=1)) is session


def test_consecutive_answers_refresh_and_card_transitions(questions, template, effects):
    factory = CardFactory(Random(42))
    created = GameSession(uuid4(), START)
    card = draw(factory, questions, template, effects, created)
    session = created.activate(card, now=START)
    assert session.player == PlayerState(100, 0, 0)
    assert session.remaining_time_ms == 60_000
    assert session.phase is GamePhase.AWAITING_ANSWER
    assert session.last_answer_result is None

    # Literal totals include seeded effects, one second to answer, and one second between cards.
    expected = (
        (True, 30, 30, 1, 110, 59_000),
        (True, 30, 60, 2, 120, 57_000),
        (True, 23, 83, 3, 120, 58_000),
        (True, 23, 106, 4, 120, 59_000),
        (True, 30, 136, 5, 130, 57_000),
        (False, 0, 136, 0, 130, 50_000),
        (True, 30, 166, 1, 140, 51_000),
    )
    now = START
    seen = set()
    snapshots = []
    for index, (correct, delta, score, streak, hp, time_ms) in enumerate(expected):
        seen.add(session.current_card.question.id)
        before = session
        snapshots.append((before, before.player, before.used_question_ids, before.last_answer_result))
        now += timedelta(seconds=1)
        session = submit(session, correct, now)
        assert session is not before
        assert session.player == PlayerState(hp, score, streak)
        assert session.remaining_time_ms == time_ms
        assert session.status is GameStatus.ACTIVE
        assert session.phase is GamePhase.AWAITING_NEXT_CARD
        assert session.game_over_reason is None
        assert session.used_question_ids == frozenset(seen)
        result = session.last_answer_result
        assert result.card_id == before.current_card.id
        assert result.is_correct is correct
        assert result.score_delta == delta
        assert result.correct_answer_id == before.current_card.question.correct_answer_id
        trigger = EffectTrigger.CORRECT if correct else EffectTrigger.INCORRECT
        assert result.applied_effects == tuple(e for e in before.current_card.effects if e.trigger is trigger)
        now += timedelta(milliseconds=500)
        refreshed = session.refresh(now=now)
        assert refreshed.last_answer_result is result
        assert refreshed.player == session.player
        assert refreshed.remaining_time_ms == time_ms - 500
        session = refreshed
        if index < len(expected) - 1:
            card = draw(factory, questions, template, effects, session)
            now += timedelta(milliseconds=500)
            session = session.assign_next_card(card, now=now)
            assert session.last_answer_result is None
            assert session.phase is GamePhase.AWAITING_ANSWER
            assert session.remaining_time_ms == time_ms - 1000
    assert seen == {q.id for q in questions}
    assert created.player == PlayerState()
    assert created.used_question_ids == frozenset()
    for snapshot, player, used_ids, result in snapshots:
        assert snapshot.player == player
        assert snapshot.used_question_ids == used_ids
        assert snapshot.last_answer_result is result


@pytest.mark.parametrize("elapsed_ms,accepted", [(59_999, True), (60_000, False)])
def test_answer_expiry_boundary_with_generated_bonus_card(questions, template, effects, elapsed_ms, accepted):
    factory = CardFactory(Random(42))
    time_bonus = tuple(e for e in effects if e.type is EffectType.TIME)
    created = GameSession(uuid4(), START)
    card = draw(factory, questions, template, time_bonus, created)
    active = created.activate(card, now=START)
    now = START + timedelta(milliseconds=elapsed_ms)
    result = submit(active, True, now)
    if accepted:
        assert result.player == PlayerState(100, 15, 1)
        assert result.remaining_time_ms == 3001
        assert result.phase is GamePhase.AWAITING_NEXT_CARD
        assert result.status is GameStatus.ACTIVE
        assert result.game_over_reason is None
        assert result.last_answer_result.score_delta == 15
    else:
        assert result.player == PlayerState()
        assert result.remaining_time_ms == 0
        assert result.phase is None
        assert result.game_over_reason is GameOverReason.TIME_EXPIRED
        assert result.status is GameStatus.FINISHED
        assert result.last_answer_result is None
        assert_finished_rejects_gameplay(result, card, now)


@pytest.mark.parametrize("waiting_for_next", [False, True])
def test_expiration_during_the_game_loop(questions, template, effects, waiting_for_next):
    factory = CardFactory(Random(42))
    created = GameSession(uuid4(), START)
    first = draw(factory, questions, template, effects, created)
    evaluated = submit(created.activate(first, now=START), True, START + timedelta(seconds=1))
    assert evaluated.player == PlayerState(110, 30, 1)
    assert evaluated.remaining_time_ms == 59_000
    prepared = draw(factory, questions, template, effects, evaluated)
    if waiting_for_next:
        expired = evaluated.assign_next_card(prepared, now=START + timedelta(seconds=60))
        assert expired.last_answer_result is evaluated.last_answer_result
        assert expired.used_question_ids == evaluated.used_question_ids
        assert expired.current_card is first
    else:
        assigned = evaluated.assign_next_card(prepared, now=START + timedelta(seconds=2))
        expired = submit(assigned, True, START + timedelta(seconds=60))
        assert expired.last_answer_result is None
        assert expired.used_question_ids == frozenset({first.question.id, prepared.question.id})
    assert expired.player == PlayerState(110, 30, 1)
    assert expired.remaining_time_ms == 0
    assert expired.status is GameStatus.FINISHED
    assert expired.phase is None
    assert expired.game_over_reason is GameOverReason.TIME_EXPIRED
    assert_finished_rejects_gameplay(expired, prepared, START + timedelta(seconds=60))


@pytest.mark.parametrize("simultaneous", [False, True])
def test_hp_depletion_after_consecutive_generated_cards(questions, effects, simultaneous):
    factory = CardFactory(Random(42))
    template = CardTemplate(UUID(int=101), CardRarity.COMMON, 2, 2, 0, 2)
    hp_penalty = tuple(e for e in effects if e.trigger is EffectTrigger.INCORRECT and e.type is EffectType.HP)
    created = GameSession(uuid4(), START)
    card = draw(factory, questions, template, hp_penalty, created)
    session = created.activate(card, now=START)
    for index, expected_hp in enumerate((80, 60, 40, 20, 0)):
        now = START + timedelta(seconds=index + 1)
        if simultaneous and index == 4:
            now = START + timedelta(seconds=55)
        session = submit(session, False, now)
        assert session.player == PlayerState(expected_hp, 0, 0)
        assert session.remaining_time_ms == (0 if simultaneous and index == 4 else 59_000 - index * 1000)
        assert session.last_answer_result.is_correct is False
        if index < 4:
            assert session.phase is GamePhase.AWAITING_NEXT_CARD
            definitions = hp_penalty
            if simultaneous and index == 3:
                definitions = tuple(e for e in effects if e.trigger is EffectTrigger.INCORRECT
                                    and e.type in (EffectType.HP, EffectType.TIME))
                factory = CardFactory(Random(0))
            card = draw(factory, questions, template, definitions, session)
            if simultaneous and index == 3:
                assert {e.type for e in card.effects} == {EffectType.HP, EffectType.TIME}
            session = session.assign_next_card(card, now=now)
    assert session.status is GameStatus.FINISHED
    assert session.phase is None
    assert session.game_over_reason is GameOverReason.HP_DEPLETED
    assert len(session.used_question_ids) == 5
    assert_finished_rejects_gameplay(session, card, now)


def test_question_exhaustion_preserves_session_and_expiry_wins(questions, template, effects):
    factory = CardFactory(Random(42))
    pool = questions[:2]
    hp_bonus = tuple(e for e in effects if e.type is EffectType.HP)
    created = GameSession(uuid4(), START)
    card = draw(factory, pool, template, hp_bonus, created)
    session = created.activate(card, now=START)
    session = submit(session, True, START + timedelta(seconds=1))
    card = draw(factory, pool, template, hp_bonus, session)
    session = session.assign_next_card(card, now=START + timedelta(seconds=2))
    session = submit(session, True, START + timedelta(seconds=3))
    assert session.player == PlayerState(120, 30, 2)
    assert session.remaining_time_ms == 57_000
    assert session.used_question_ids == frozenset(q.id for q in pool)
    result = session.last_answer_result
    assert factory.draw(pool, (template,), hp_bonus, session.used_question_ids) is None
    assert session.status is GameStatus.ACTIVE
    assert session.phase is GamePhase.AWAITING_NEXT_CARD
    assert session.game_over_reason is None
    assert session.last_answer_result is result

    # Future NextCard orchestration must refresh and honor expiry before handling exhaustion.
    expired = session.refresh(now=START + timedelta(seconds=60))
    assert factory.draw(pool, (template,), hp_bonus, expired.used_question_ids) is None
    assert expired.game_over_reason is GameOverReason.TIME_EXPIRED
    assert expired.remaining_time_ms == 0
    assert expired.player == PlayerState(120, 30, 2)
    assert expired.last_answer_result is result


def test_play_again_is_independent_and_reopens_used_questions(questions, template, effects):
    factory = CardFactory(Random(42))
    pool = questions[:1]
    effects = tuple(e for e in effects if e.type is EffectType.HP)
    created = GameSession(uuid4(), START)
    first = draw(factory, pool, template, effects, created)
    evaluated = submit(created.activate(first, now=START), True, START + timedelta(seconds=1))
    finished = evaluated.refresh(now=START + timedelta(seconds=60))
    assert finished.player == PlayerState(110, 15, 1)
    assert finished.game_over_reason is GameOverReason.TIME_EXPIRED
    assert factory.draw(pool, (template,), effects, finished.used_question_ids) is None

    later = START + timedelta(minutes=2)
    fresh = GameSession(uuid4(), later)
    assert fresh.id != finished.id
    assert fresh.player == PlayerState()
    assert fresh.remaining_time_ms == 60_000
    assert fresh.used_question_ids == frozenset()
    assert fresh.last_answer_result is None
    assert fresh.game_over_reason is None
    second = draw(factory, pool, template, effects, fresh)
    assert second.question.id == first.question.id
    assert second.id != first.id
    restarted = fresh.activate(second, now=later)
    assert restarted.phase is GamePhase.AWAITING_ANSWER
    assert restarted.player == PlayerState()
    assert restarted.remaining_time_ms == 60_000
    submit(restarted, True, later + timedelta(seconds=1))
    assert finished.player == PlayerState(110, 15, 1)
    assert finished.remaining_time_ms == 0
    assert finished.status is GameStatus.FINISHED
    assert finished.last_answer_result is evaluated.last_answer_result
