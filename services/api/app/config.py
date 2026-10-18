from functools import lru_cache
from typing import Literal

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

    llm_provider: str = "echo"
    llm_fallback_providers: str = "echo"
    llm_user_request_limit: int = 0
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:9b"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 30.0
    llm_max_tokens: int = 512
    llm_temperature: float = 0.7

    rate_limit_per_minute: int = 0
    rate_limit_backend: Literal["memory", "db"] = "memory"

    auth_allow_legacy_tokens: bool = True

    admin_token_refs: str = ""

    @property
    def admin_refs(self) -> set[str]:
        """`token_ref`, получающие роль `admin` (админ-кабинет, OQ-3)."""
        return {item.strip() for item in self.admin_token_refs.split(",") if item.strip()}

    vision_provider: str = "ollama"
    vision_fallback_providers: str = ""
    vision_model: str = "qwen3.5:9b"
    vision_ollama_base_url: str = "http://localhost:11434"
    vision_max_tokens: int = 512
    vision_temperature: float = 0.2
    vision_prompt: str = (
        "Опиши кратко, что видно в кадре окна диалога знакомств: последние сообщения "
        "собеседника и общий тон переписки. Не выдумывай деталей, которых не видно."
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
