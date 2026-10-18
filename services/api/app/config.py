from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="MATCH_",
        extra="ignore",
    )

    environment: str = "development"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+asyncpg://match:match@localhost:5432/match"


@lru_cache
def get_settings() -> Settings:
    return Settings()
