from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID

from app.domain.card import DrawnCard
from app.domain.effect import Effect, EffectTrigger
from app.domain.effect_applier import EffectApplier
from app.domain.player import PlayerState
from app.domain.score_calculator import ScoreCalculator
from app.domain.streak_policy import StreakPolicy


class GameStatus(StrEnum):
    CREATED = "created"
    ACTIVE = "active"
    FINISHED = "finished"


class GamePhase(StrEnum):
    AWAITING_CARD = "awaiting_card"
    AWAITING_ANSWER = "awaiting_answer"
    AWAITING_NEXT_CARD = "awaiting_next_card"


class GameOverReason(StrEnum):
    HP_DEPLETED = "hp_depleted"
    TIME_EXPIRED = "time_expired"
    NO_QUESTIONS_AVAILABLE = "no_questions_available"


@dataclass(frozen=True)
class AnswerResult:
    card_id: UUID
    answer_option_id: UUID
    is_correct: bool
    correct_answer_id: UUID
    score_delta: int
    applied_effects: tuple[Effect, ...]

    def __post_init__(self) -> None:
        for value in (self.card_id, self.answer_option_id, self.correct_answer_id):
            if not isinstance(value, UUID):
                raise TypeError("answer result IDs must be UUID values")
        if type(self.is_correct) is not bool:
            raise TypeError("is_correct must be a boolean")
        if type(self.score_delta) is not int:
            raise TypeError("score delta must be an integer")
        object.__setattr__(self, "applied_effects", tuple(self.applied_effects))
        trigger = EffectTrigger.CORRECT if self.is_correct else EffectTrigger.INCORRECT
        for effect in self.applied_effects:
            if not isinstance(effect, Effect):
                raise TypeError("applied effects must contain Effect values")
            if effect.trigger is not trigger:
                raise ValueError("applied effects must match the answer outcome")
        if self.is_correct != (self.answer_option_id == self.correct_answer_id):
            raise ValueError("answer result correctness must match its IDs")


@dataclass(frozen=True)
class GameSession:
    id: UUID
    last_updated_at: datetime
    status: GameStatus = GameStatus.CREATED
    phase: GamePhase | None = GamePhase.AWAITING_CARD
    player: PlayerState = field(default_factory=PlayerState)
    remaining_time_ms: int = 60_000
    current_card: DrawnCard | None = None
    used_question_ids: frozenset[UUID] = field(default_factory=frozenset)
    game_over_reason: GameOverReason | None = None
    last_answer_result: AnswerResult | None = None

    def __post_init__(self) -> None:
        self._validate_enum_types()
        self._validate_time()
        object.__setattr__(self, "used_question_ids", frozenset(self.used_question_ids))
        self._validate_status_and_phase()
        self._validate_current_question()
        self._validate_answer_result()

    def activate(self, card: DrawnCard, *, now: datetime) -> GameSession:
        self._validate_now(now)
        self._validate_card(card)
        if self.status is not GameStatus.CREATED:
            raise ValueError("only a created session can be activated")
        if (self.player != PlayerState() or self.remaining_time_ms != 60_000
                or self.used_question_ids):
            raise ValueError("activation requires fresh initial state")
        return replace(
            self, status=GameStatus.ACTIVE, phase=GamePhase.AWAITING_ANSWER,
            current_card=card, used_question_ids=frozenset({card.question.id}),
            last_updated_at=now,
        )

    def submit_answer(
        self, card_id: UUID, answer_option_id: UUID, *, now: datetime,
    ) -> GameSession:
        self._validate_now(now)
        if not isinstance(card_id, UUID) or not isinstance(answer_option_id, UUID):
            raise TypeError("card and answer option IDs must be UUID values")
        self._require_active()
        session = self.refresh(now=now)
        if session.status is GameStatus.FINISHED:
            return session
        if session.phase is not GamePhase.AWAITING_ANSWER:
            raise ValueError("session is not awaiting an answer")
        card = session.current_card
        assert card is not None
        if card.id != card_id:
            raise ValueError("submitted card is not the current card")
        if answer_option_id not in {option.id for option in card.question.options}:
            raise ValueError("answer option does not belong to the current question")

        is_correct = answer_option_id == card.question.correct_answer_id
        streak = StreakPolicy.next_streak(session.player.correct_streak, is_correct)
        score_delta = ScoreCalculator.calculate(
            card.question.difficulty, is_correct, streak, card.effects,
        )
        player = replace(
            session.player, correct_streak=streak, score=session.player.score + score_delta,
        )
        player, remaining = EffectApplier.apply(
            player, session.remaining_time_ms, is_correct, card.effects,
        )
        trigger = EffectTrigger.CORRECT if is_correct else EffectTrigger.INCORRECT
        result = AnswerResult(
            card.id, answer_option_id, is_correct, card.question.correct_answer_id,
            score_delta, tuple(effect for effect in card.effects if effect.trigger is trigger),
        )
        session = replace(
            session, player=player, remaining_time_ms=remaining,
            phase=GamePhase.AWAITING_NEXT_CARD, last_answer_result=result,
        )
        if player.hp <= 0:
            return session._finish(GameOverReason.HP_DEPLETED)
        if remaining == 0:
            return session._finish(GameOverReason.TIME_EXPIRED)
        return session

    def assign_next_card(self, card: DrawnCard, *, now: datetime) -> GameSession:
        self._validate_now(now)
        self._validate_card(card)
        self._require_active()
        session = self.refresh(now=now)
        if session.status is GameStatus.FINISHED:
            return session
        if session.phase is not GamePhase.AWAITING_NEXT_CARD:
            raise ValueError("session is not awaiting the next card")
        if card.question.id in session.used_question_ids:
            raise ValueError("question has already been used in this session")
        return replace(
            session, current_card=card, phase=GamePhase.AWAITING_ANSWER,
            used_question_ids=session.used_question_ids | {card.question.id},
            last_answer_result=None,
        )

    def refresh(self, *, now: datetime) -> GameSession:
        self._validate_now(now)
        if self.status is not GameStatus.ACTIVE:
            return self
        reference = self.last_updated_at.astimezone(UTC)
        elapsed_ms = (now.astimezone(UTC) - reference) // timedelta(milliseconds=1)
        session = replace(
            self, remaining_time_ms=max(0, self.remaining_time_ms - elapsed_ms),
            last_updated_at=reference + timedelta(milliseconds=elapsed_ms),
        )
        if session.remaining_time_ms == 0:
            return session._finish(GameOverReason.TIME_EXPIRED)
        if session.player.hp <= 0:
            return session._finish(GameOverReason.HP_DEPLETED)
        return session

    def _finish(self, reason: GameOverReason) -> GameSession:
        return replace(self, status=GameStatus.FINISHED, phase=None, game_over_reason=reason)

    def _require_active(self) -> None:
        if self.status is not GameStatus.ACTIVE:
            raise ValueError("session must be active")

    @staticmethod
    def _validate_card(card: DrawnCard) -> None:
        if not isinstance(card, DrawnCard):
            raise TypeError("card must be a DrawnCard")

    @staticmethod
    def _validate_timestamp(timestamp: datetime) -> None:
        if not isinstance(timestamp, datetime):
            raise TypeError("timestamp must be a datetime")
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")

    def _validate_now(self, now: datetime) -> None:
        self._validate_timestamp(now)
        if now.astimezone(UTC) < self.last_updated_at.astimezone(UTC):
            raise ValueError("timestamp cannot precede the stored time reference")

    def _validate_enum_types(self) -> None:
        if not isinstance(self.status, GameStatus):
            raise TypeError("status must be a GameStatus")
        if self.phase is not None and not isinstance(self.phase, GamePhase):
            raise TypeError("phase must be a GamePhase or None")
        if self.game_over_reason is not None and not isinstance(
            self.game_over_reason, GameOverReason
        ):
            raise TypeError("game_over_reason must be a GameOverReason or None")

    def _validate_time(self) -> None:
        if type(self.remaining_time_ms) is not int:
            raise TypeError("remaining time must be integer milliseconds")
        if self.remaining_time_ms < 0:
            raise ValueError("remaining time cannot be negative")
        self._validate_timestamp(self.last_updated_at)

    def _validate_status_and_phase(self) -> None:
        if self.status is GameStatus.FINISHED:
            if self.phase is not None or self.game_over_reason is None:
                raise ValueError("finished sessions require a reason and no phase")
        else:
            if self.game_over_reason is not None:
                raise ValueError("unfinished sessions cannot have a game-over reason")
            if self.status is GameStatus.CREATED:
                if self.phase is not GamePhase.AWAITING_CARD or self.current_card is not None:
                    raise ValueError("created sessions must await their first card")
            elif (
                self.phase not in (
                    GamePhase.AWAITING_ANSWER, GamePhase.AWAITING_NEXT_CARD
                )
                or self.current_card is None
            ):
                raise ValueError("active sessions require a current card and active phase")

    def _validate_current_question(self) -> None:
        if (
            self.current_card is not None
            and self.current_card.question.id not in self.used_question_ids
        ):
            raise ValueError("current question must be recorded as used")

    def _validate_answer_result(self) -> None:
        result = self.last_answer_result
        if result is None:
            return
        if not isinstance(result, AnswerResult):
            raise TypeError("last answer result must be an AnswerResult or None")
        if self.status is GameStatus.CREATED or self.phase is GamePhase.AWAITING_ANSWER:
            raise ValueError("an unanswered session cannot contain an answer result")
        card = self.current_card
        if card is None or result.card_id != card.id:
            raise ValueError("answer result must belong to the current card")
        if (result.correct_answer_id != card.question.correct_answer_id
                or result.answer_option_id not in {option.id for option in card.question.options}):
            raise ValueError("answer result must match the current question")
