from functools import lru_cache

from app.config import Settings, get_settings
from app.vision.base import VisionProvider, VisionRequest, VisionResponse
from app.vision.providers import OllamaVisionProvider, OpenAICompatVisionProvider


class VisionUnavailable(RuntimeError):
    pass


def _provider_names(settings: Settings) -> list[str]:
    raw = [settings.vision_provider, *settings.vision_fallback_providers.split(",")]
    names: list[str] = []
    for name in raw:
        name = name.strip()
        if name and name not in names:
            names.append(name)
    return names


def _build_provider(name: str, settings: Settings) -> VisionProvider | None:
    if name == "ollama":
        return OllamaVisionProvider(
            settings.vision_ollama_base_url,
            settings.vision_model,
            settings.llm_timeout_seconds,
        )
    if name == "openai":
        if not settings.openai_api_key:
            return None
        return OpenAICompatVisionProvider(
            settings.openai_base_url,
            settings.openai_api_key,
            settings.vision_model,
            settings.llm_timeout_seconds,
        )
    return None


def build_providers(settings: Settings) -> list[VisionProvider]:
    return [
        provider
        for name in _provider_names(settings)
        if (provider := _build_provider(name, settings)) is not None
    ]


class VisionGateway:
    def __init__(self, providers: list[VisionProvider]) -> None:
        self._providers = providers

    @property
    def provider_names(self) -> list[str]:
        return [provider.name for provider in self._providers]

    @property
    def available(self) -> bool:
        return bool(self._providers)

    async def analyze(self, request: VisionRequest) -> VisionResponse:
        if not self._providers:
            raise VisionUnavailable("no vision provider configured")
        errors: list[str] = []
        for provider in self._providers:
            try:
                response = await provider.analyze(request)
            except Exception as exc:
                errors.append(f"{provider.name}: {exc}")
                continue
            if response.text.strip():
                return response
            errors.append(f"{provider.name}: empty response")
        raise VisionUnavailable("; ".join(errors))


@lru_cache
def get_vision_gateway() -> VisionGateway:
    return VisionGateway(build_providers(get_settings()))
