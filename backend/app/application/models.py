from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

from app.domain.card import CardTemplate
from app.domain.effect import Effect, EffectDefinition
from app.domain.game_session import GameSession
from app.domain.question import Question


class ExpiryPolicy(StrEnum):
    RENEW_ACTIVITY = "renew_activity"
    PRESERVE = "preserve"


@dataclass(frozen=True)
class GameCatalogs:
    questions: tuple[Question, ...]
    templates: tuple[CardTemplate, ...]
    effect_definitions: tuple[EffectDefinition, ...]


@dataclass(frozen=True)
class StoredSession:
    session: GameSession
    version: int
    token_verifier: bytes = field(repr=False)


@dataclass(frozen=True)
class IssuedToken:
    token: str = field(repr=False)
    verifier: bytes = field(repr=False)


@dataclass(frozen=True)
class PlayerView:
    hp: int
    score: int
    correct_streak: int


@dataclass(frozen=True)
class EffectView:
    type: str
    value: int
    trigger: str


@dataclass(frozen=True)
class OptionView:
    id: UUID
    text: str


@dataclass(frozen=True)
class QuestionView:
    id: UUID
    text: str
    category: str
    difficulty: int
    options: tuple[OptionView, ...]


@dataclass(frozen=True)
class CardView:
    id: UUID
    rarity: str
    question: QuestionView
    effects: tuple[EffectView, ...]


@dataclass(frozen=True)
class AnswerFeedback:
    card_id: UUID
    answer_option_id: UUID
    is_correct: bool
    correct_answer_id: UUID
    score_delta: int
    applied_effects: tuple[EffectView, ...]


@dataclass(frozen=True)
class GameState:
    id: UUID
    status: str
    phase: str | None
    player: PlayerView
    remaining_time_ms: int
    card: CardView | None
    game_over_reason: str | None
    last_answer_result: AnswerFeedback | None

    @classmethod
    def from_session(cls, session: GameSession) -> GameState:
        def effects(values: tuple[Effect, ...]) -> tuple[EffectView, ...]:
            return tuple(EffectView(e.type.value, e.value, e.trigger.value) for e in values)

        card = session.current_card
        card_view = None
        if card is not None:
            q = card.question
            card_view = CardView(
                card.id, card.template.rarity.value,
                QuestionView(q.id, q.text, q.category.value, q.difficulty,
                             tuple(OptionView(o.id, o.text) for o in q.options)),
                effects(card.effects),
            )
        result = session.last_answer_result
        feedback = None if result is None else AnswerFeedback(
            result.card_id, result.answer_option_id, result.is_correct,
            result.correct_answer_id, result.score_delta, effects(result.applied_effects),
        )
        return cls(
            session.id, session.status.value,
            None if session.phase is None else session.phase.value,
            PlayerView(session.player.hp, session.player.score, session.player.correct_streak),
            session.remaining_time_ms, card_view,
            None if session.game_over_reason is None else session.game_over_reason.value,
            feedback,
        )


@dataclass(frozen=True)
class StartedGame:
    state: GameState
    token: str = field(repr=False)


@dataclass(frozen=True)
class AnswerSubmission:
    state: GameState
    accepted: bool
