from contextlib import AsyncExitStack, asynccontextmanager
from datetime import UTC, datetime
from random import Random
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException

from app.api.games import GameServices, router
from app.application import errors
from app.application.get_game_state import GetGameState
from app.application.start_game import StartGame
from app.config import Settings
from app.domain.card_factory import CardFactory
from app.persistence.catalog import SQLAlchemyCatalogRepository
from app.persistence.database import create_database_engine, create_session_factory
from app.persistence.redis_sessions import RedisSessionRepository, create_redis_client
from app.security.session_tokens import SecureSessionTokens


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class HealthResponse(BaseModel):
    status: Literal['ok'] = 'ok'


_ERROR_MAP = {
    errors.SessionUnavailable: (404, 'SESSION_UNAVAILABLE', 'Session unavailable.'),
    errors.NoPlayableQuestions: (503, 'NO_PLAYABLE_QUESTIONS', 'No playable questions are available.'),
    errors.CatalogFailure: (503, 'SERVICE_UNAVAILABLE', 'The game service is temporarily unavailable.'),
    errors.PersistenceFailure: (503, 'SERVICE_UNAVAILABLE', 'The game service is temporarily unavailable.'),
    errors.ConcurrentUpdate: (409, 'CONCURRENT_UPDATE', 'The session changed. Please try again.'),
    errors.InvalidGamePhase: (409, 'INVALID_GAME_PHASE', 'This action is not available in the current phase.'),
    errors.GameAlreadyFinished: (409, 'GAME_ALREADY_FINISHED', 'The game has finished.'),
    errors.StaleCard: (409, 'STALE_CARD', 'This card is no longer current.'),
    errors.InvalidAnswerOption: (400, 'INVALID_ANSWER_OPTION', 'Invalid answer option.'),
}


def error_response(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={'error': {'code': code, 'message': message}},
                        headers={'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with AsyncExitStack() as resources:
            engine = create_database_engine(settings.database_url)
            resources.push_async_callback(engine.dispose)
            redis = create_redis_client(settings.redis_url)
            resources.push_async_callback(redis.aclose)
            catalogs = SQLAlchemyCatalogRepository(create_session_factory(engine))
            sessions = RedisSessionRepository(redis, catalogs.load_card_content)
            tokens, clock = SecureSessionTokens(), SystemClock()
            app.state.games = GameServices(
                StartGame(sessions, catalogs, clock, tokens, lambda: CardFactory(Random())),
                GetGameState(sessions, clock, tokens),
            )
            try:
                yield
            finally:
                del app.state.games

    app = FastAPI(title=settings.name, debug=settings.debug, lifespan=lifespan)

    @app.middleware('http')
    async def protect_game_responses(request: Request, call_next):
        if not request.url.path.startswith('/api/v1/games'):
            return await call_next(request)
        try:
            response = await call_next(request)
        except Exception:
            # Do not expose exception payloads or credentials, even in debug mode.
            return error_response(500, 'INTERNAL_ERROR', 'An unexpected error occurred.')
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.exception_handler(errors.ApplicationError)
    async def application_error(request: Request, exc: errors.ApplicationError):
        return error_response(*_ERROR_MAP.get(type(exc), (500, 'INTERNAL_ERROR', 'An unexpected error occurred.')))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return error_response(422, 'INVALID_REQUEST', 'Invalid request parameters.')

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return error_response(exc.status_code, 'HTTP_ERROR', 'The requested operation is unavailable.')

    @app.get('/health', response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse()

    app.include_router(router)
    return app


app = create_app()
