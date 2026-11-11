from dataclasses import asdict
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.application.models import GameState


class DTO(BaseModel):
    model_config = ConfigDict(extra='forbid')


class SessionRequest(DTO):
    game_id: UUID
    session_token: SecretStr = Field(repr=False)


class PlayerResponse(DTO):
    hp: int
    score: int
    correct_streak: int


class EffectResponse(DTO):
    type: Literal['hp', 'score', 'time']
    value: int
    trigger: Literal['correct', 'incorrect']


class OptionResponse(DTO):
    id: UUID
    text: str


class QuestionResponse(DTO):
    id: UUID
    text: str
    category: str
    difficulty: int
    options: list[OptionResponse] = Field(min_length=4, max_length=4)


class CardResponse(DTO):
    id: UUID
    rarity: Literal['common', 'rare', 'epic']
    question: QuestionResponse
    effects: list[EffectResponse]


class FeedbackResponse(DTO):
    card_id: UUID
    answer_option_id: UUID
    is_correct: bool
    correct_answer_id: UUID
    score_delta: int
    applied_effects: list[EffectResponse]


class GameResponse(DTO):
    game_id: UUID
    status: Literal['created', 'active', 'finished']
    phase: Literal['awaiting_card', 'awaiting_answer', 'awaiting_next_card'] | None
    player: PlayerResponse
    remaining_time_ms: int = Field(ge=0)
    card: CardResponse | None
    game_over_reason: Literal['hp_depleted', 'time_expired', 'no_questions_available'] | None
    last_answer_result: FeedbackResponse | None

    @classmethod
    def from_state(cls, state: GameState) -> GameResponse:
        values = asdict(state)
        values['game_id'] = values.pop('id')
        return cls.model_validate(values)


class StartedGameResponse(GameResponse):
    session_token: str = Field(repr=False)


class ErrorDetail(DTO):
    code: str
    message: str


class ErrorResponse(DTO):
    error: ErrorDetail
