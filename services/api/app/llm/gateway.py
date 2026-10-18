from functools import lru_cache

from app.config import Settings, get_settings
from app.llm.base import LLMProvider, LLMRequest, LLMResponse
from app.llm.echo import EchoProvider
from app.llm.ollama import OllamaProvider


def build_provider(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "ollama":
        return OllamaProvider(
            settings.ollama_base_url,
            settings.ollama_model,
            settings.llm_timeout_seconds,
        )
    return EchoProvider()


class LLMGateway:
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    @property
    def provider_name(self) -> str:
        return self._provider.name

    async def generate(self, request: LLMRequest) -> LLMResponse:
        return await self._provider.generate(request)


@lru_cache
def get_gateway() -> LLMGateway:
    return LLMGateway(build_provider(get_settings()))
