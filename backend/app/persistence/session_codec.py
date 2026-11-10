"""Versioned dynamic session snapshots; static card content stays in PostgreSQL."""
from dataclasses import asdict
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.application.errors import PersistenceFailure
from app.application.models import StoredSession
from app.domain.card import CardTemplate, DrawnCard
from app.domain.effect import Effect, EffectTrigger, EffectType
from app.domain.game_session import AnswerResult, GameOverReason, GamePhase, GameSession, GameStatus
from app.domain.player import PlayerState
from app.domain.question import Question


class SnapshotModel(BaseModel):
    model_config = ConfigDict(strict=True, extra='forbid', frozen=True, hide_input_in_errors=True)


class EffectSnapshot(SnapshotModel):
    type: EffectType
    value: int
    trigger: EffectTrigger

    def hydrate(self) -> Effect:
        return Effect(self.type, self.value, self.trigger)


class PlayerSnapshot(SnapshotModel):
    hp: int
    score: int
    correct_streak: int = Field(ge=0)


class CardSnapshot(SnapshotModel):
    id: UUID
    question_id: UUID
    template_id: UUID
    effects: tuple[EffectSnapshot, ...]


class FeedbackSnapshot(SnapshotModel):
    card_id: UUID
    answer_option_id: UUID
    is_correct: bool
    correct_answer_id: UUID
    score_delta: int
    applied_effects: tuple[EffectSnapshot, ...]

    def hydrate(self) -> AnswerResult:
        return AnswerResult(
            self.card_id, self.answer_option_id, self.is_correct, self.correct_answer_id,
            self.score_delta, tuple(e.hydrate() for e in self.applied_effects),
        )


class SessionSnapshot(SnapshotModel):
    schema_version: Literal[1]
    version: int = Field(ge=0)
    token_verifier: str = Field(pattern=r'^[0-9a-f]{64}$', repr=False)
    id: UUID
    last_updated_at: AwareDatetime
    status: GameStatus
    phase: GamePhase | None
    player: PlayerSnapshot
    remaining_time_ms: int = Field(ge=0)
    current_card: CardSnapshot | None
    used_question_ids: tuple[UUID, ...]
    game_over_reason: GameOverReason | None
    last_answer_result: FeedbackSnapshot | None

    @field_validator("schema_version", mode="before")
    @classmethod
    def validate_schema_version(cls, value: object) -> object:
        if type(value) is not int or value != 1:
            raise ValueError("unsupported schema version")
        return value

    @model_validator(mode='after')
    def validate_snapshot(self) -> SessionSnapshot:
        if len(set(self.used_question_ids)) != len(self.used_question_ids):
            raise ValueError('duplicate used question IDs')
        if self.status is GameStatus.FINISHED:
            if self.phase is not None or self.game_over_reason is None:
                raise ValueError('invalid finished state')
        elif self.game_over_reason is not None:
            raise ValueError('unfinished session has a game-over reason')
        if self.status is GameStatus.CREATED:
            if self.phase is not GamePhase.AWAITING_CARD or self.current_card is not None:
                raise ValueError('invalid created state')
        if self.status is GameStatus.ACTIVE:
            if self.phase not in (GamePhase.AWAITING_ANSWER, GamePhase.AWAITING_NEXT_CARD) or self.current_card is None:
                raise ValueError('invalid active state')
        if self.current_card is not None:
            if self.current_card.question_id not in self.used_question_ids:
                raise ValueError('current question is not recorded as used')
            for effect in self.current_card.effects:
                effect.hydrate()
        if self.last_answer_result is not None:
            self.last_answer_result.hydrate()
            if self.current_card is None or self.current_card.id != self.last_answer_result.card_id:
                raise ValueError('feedback belongs to a different card')
            if self.status is GameStatus.CREATED or self.phase is GamePhase.AWAITING_ANSWER:
                raise ValueError('unanswered state contains feedback')
        elif self.phase is GamePhase.AWAITING_NEXT_CARD:
            raise ValueError('answered state requires feedback')
        return self

    def hydrate(self, question: Question | None = None, template: CardTemplate | None = None) -> StoredSession:
        try:
            card = None
            if self.current_card is not None:
                saved = self.current_card
                if question is None or template is None or question.id != saved.question_id or template.id != saved.template_id:
                    raise ValueError('missing or mismatched static content')
                card = DrawnCard(saved.id, template, question, tuple(e.hydrate() for e in saved.effects))
            result = None if self.last_answer_result is None else self.last_answer_result.hydrate()
            if result is not None and card is not None:
                trigger = EffectTrigger.CORRECT if result.is_correct else EffectTrigger.INCORRECT
                if result.applied_effects != tuple(e for e in card.effects if e.trigger is trigger):
                    raise ValueError('feedback effects do not match the card')
            session = GameSession(
                id=self.id, last_updated_at=self.last_updated_at, status=self.status, phase=self.phase,
                player=PlayerState(**self.player.model_dump()), remaining_time_ms=self.remaining_time_ms,
                current_card=card, used_question_ids=frozenset(self.used_question_ids),
                game_over_reason=self.game_over_reason, last_answer_result=result,
            )
            return StoredSession(session, self.version, bytes.fromhex(self.token_verifier))
        except (ValueError, TypeError):
            raise PersistenceFailure('Invalid session snapshot') from None


def decode_snapshot(data: bytes | str, session_id: UUID) -> SessionSnapshot:
    try:
        snapshot = SessionSnapshot.model_validate_json(data)
        if snapshot.id != session_id:
            raise ValueError('session ID mismatch')
        return snapshot
    except (ValueError, TypeError):
        raise PersistenceFailure('Invalid or unsupported session snapshot') from None


def encode_snapshot(session: GameSession, version: int, verifier: bytes) -> str:
    try:
        if not isinstance(verifier, bytes) or len(verifier) != 32:
            raise ValueError('invalid verifier')
        card = session.current_card
        snapshot = SessionSnapshot(
            schema_version=1, version=version, token_verifier=verifier.hex(),
            id=session.id, last_updated_at=session.last_updated_at,
            status=session.status, phase=session.phase,
            player=PlayerSnapshot(**asdict(session.player)), remaining_time_ms=session.remaining_time_ms,
            current_card=None if card is None else CardSnapshot(
                id=card.id, question_id=card.question.id, template_id=card.template.id,
                effects=tuple(EffectSnapshot(**asdict(e)) for e in card.effects),
            ),
            used_question_ids=tuple(sorted(session.used_question_ids)), game_over_reason=session.game_over_reason,
            last_answer_result=None if session.last_answer_result is None else FeedbackSnapshot(
                **{**asdict(session.last_answer_result), 'applied_effects': tuple(
                    EffectSnapshot(**asdict(e)) for e in session.last_answer_result.applied_effects
                )},
            ),
        )
        snapshot.hydrate(None if card is None else card.question, None if card is None else card.template)
        return snapshot.model_dump_json()
    except (ValueError, TypeError):
        raise PersistenceFailure('Invalid session snapshot') from None
