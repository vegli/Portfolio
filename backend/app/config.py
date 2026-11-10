from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_", env_file=".env", env_file_encoding="utf-8"
    )

    name: str = "Developer Portfolio & Playground API"
    debug: bool = False
    database_url: str = Field(
        default="postgresql+psycopg://playground:playground@localhost:5432/playground",
        validation_alias="DATABASE_URL",
        repr=False,
    )

    redis_url: str = Field(
        default="redis://localhost:6379/0", validation_alias="REDIS_URL", repr=False,
    )
