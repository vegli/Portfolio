from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response
from pydantic import SecretStr

from app.api.schemas import ErrorResponse, GameResponse, SessionRequest, StartedGameResponse
from app.application.errors import SessionUnavailable
from app.application.get_game_state import GetGameState
from app.application.start_game import StartGame


@dataclass(frozen=True)
class GameServices:
    start: StartGame
    get: GetGameState


def get_services(request: Request) -> GameServices:
    return request.app.state.games


def session_request(
    game_id: UUID, token: Annotated[str | None, Header(alias='X-Game-Token', description='Required session credential; missing or invalid credentials return 404.')] = None,
) -> SessionRequest:
    if token is None or len(token) != 43 or not token.isascii():
        raise SessionUnavailable()
    return SessionRequest(game_id=game_id, session_token=SecretStr(token))


router = APIRouter(prefix='/api/v1/games', tags=['games'], responses={
    404: {'model': ErrorResponse}, 409: {'model': ErrorResponse},
    422: {'model': ErrorResponse}, 503: {'model': ErrorResponse},
    500: {'model': ErrorResponse},
})


@router.post('', response_model=StartedGameResponse, status_code=201)
async def start_game(response: Response, services: Annotated[GameServices, Depends(get_services)]) -> StartedGameResponse:
    result = await services.start.execute()
    state = GameResponse.from_state(result.state)
    response.headers['Location'] = f'/api/v1/games/{state.game_id}'
    return StartedGameResponse(**state.model_dump(), session_token=result.token)


@router.get('/{game_id}', response_model=GameResponse)
async def get_game(
    credentials: Annotated[SessionRequest, Depends(session_request)],
    services: Annotated[GameServices, Depends(get_services)],
) -> GameResponse:
    state = await services.get.execute(credentials.game_id, credentials.session_token.get_secret_value())
    return GameResponse.from_state(state)
