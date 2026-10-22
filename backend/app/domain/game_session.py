from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app.domain.card import DrawnCard
from app.domain.player import PlayerState


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

    def __post_init__(self) -> None:
        self._validate_enum_types()
        self._validate_time()
        object.__setattr__(self, "used_question_ids", frozenset(self.used_question_ids))
        self._validate_status_and_phase()
        self._validate_current_question()

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
        if self.last_updated_at.tzinfo is None or self.last_updated_at.utcoffset() is None:
            raise ValueError("last_updated_at must be timezone-aware")

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
