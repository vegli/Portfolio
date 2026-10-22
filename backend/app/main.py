from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from app.config import Settings

settings = Settings()
app = FastAPI(title=settings.name, debug=settings.debug)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()
