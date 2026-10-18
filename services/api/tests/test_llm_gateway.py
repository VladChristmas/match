import pytest

from app.config import Settings
from app.llm.base import LLMRequest, LLMResponse
from app.llm.echo import EchoProvider
from app.llm.gateway import LLMGateway, LLMUnavailable, build_providers


class FailingProvider:
    name = "failing"
    model = "failing"

    async def generate(self, request: LLMRequest) -> LLMResponse:
        raise RuntimeError("boom")


class EmptyProvider:
    name = "empty"
    model = "empty"

    async def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(text="   ", provider=self.name, model=self.model, latency_ms=0)


def _request() -> LLMRequest:
    return LLMRequest(task_type="test", system_prompt="sys", messages=[])


async def test_falls_back_to_next_provider():
    gateway = LLMGateway([FailingProvider(), EchoProvider()])
    response = await gateway.generate(_request())
    assert response.provider == "echo"


async def test_empty_response_triggers_fallback():
    gateway = LLMGateway([EmptyProvider(), EchoProvider()])
    response = await gateway.generate(_request())
    assert response.provider == "echo"


async def test_all_providers_failing_raises():
    gateway = LLMGateway([FailingProvider()])
    with pytest.raises(LLMUnavailable):
        await gateway.generate(_request())


def test_build_providers_dedupes_order():
    settings = Settings(llm_provider="echo", llm_fallback_providers="echo,ollama")
    names = [provider.name for provider in build_providers(settings)]
    assert names == ["echo", "ollama"]


def test_build_providers_falls_back_to_echo_when_unconfigured():
    settings = Settings(llm_provider="openai", llm_fallback_providers="")
    names = [provider.name for provider in build_providers(settings)]
    assert names == ["echo"]
