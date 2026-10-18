from functools import lru_cache

from app.config import Settings, get_settings
from app.llm.base import LLMProvider, LLMRequest, LLMResponse
from app.llm.echo import EchoProvider
from app.llm.ollama import OllamaProvider
from app.llm.openai_compat import OpenAICompatProvider


class LLMUnavailable(RuntimeError):
    pass


def _provider_names(settings: Settings) -> list[str]:
    raw = [settings.llm_provider, *settings.llm_fallback_providers.split(",")]
    names: list[str] = []
    for name in raw:
        name = name.strip()
        if name and name not in names:
            names.append(name)
    return names


def _build_provider(name: str, settings: Settings) -> LLMProvider | None:
    if name == "echo":
        return EchoProvider()
    if name == "ollama":
        return OllamaProvider(
            settings.ollama_base_url,
            settings.ollama_model,
            settings.llm_timeout_seconds,
        )
    if name == "openai":
        if not settings.openai_api_key:
            return None
        return OpenAICompatProvider(
            settings.openai_base_url,
            settings.openai_api_key,
            settings.openai_model,
            settings.llm_timeout_seconds,
        )
    return None


def build_providers(settings: Settings) -> list[LLMProvider]:
    providers = [
        provider
        for name in _provider_names(settings)
        if (provider := _build_provider(name, settings)) is not None
    ]
    return providers or [EchoProvider()]


class LLMGateway:
    def __init__(self, providers: list[LLMProvider]) -> None:
        if not providers:
            raise ValueError("At least one LLM provider is required")
        self._providers = providers

    @property
    def provider_name(self) -> str:
        return self._providers[0].name

    @property
    def provider_names(self) -> list[str]:
        return [provider.name for provider in self._providers]

    async def generate(self, request: LLMRequest) -> LLMResponse:
        errors: list[str] = []
        for provider in self._providers:
            try:
                response = await provider.generate(request)
            except Exception as exc:
                errors.append(f"{provider.name}: {exc}")
                continue
            if response.text.strip():
                return response
            errors.append(f"{provider.name}: empty response")
        raise LLMUnavailable("; ".join(errors) or "no provider produced a response")


@lru_cache
def get_gateway() -> LLMGateway:
    return LLMGateway(build_providers(get_settings()))
