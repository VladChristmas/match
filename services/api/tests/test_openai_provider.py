import httpx
import pytest

from app.llm.base import LLMRequest
from app.llm.openai_compat import OpenAICompatProvider


def _request() -> LLMRequest:
    return LLMRequest(task_type="t", system_prompt="sys", messages=[])


async def test_openai_compat_parses_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Привет!"}}],
                "usage": {"total_tokens": 12},
            },
        )

    provider = OpenAICompatProvider(
        "https://example.test/v1", "key", "model-x", transport=httpx.MockTransport(handler)
    )
    response = await provider.generate(_request())
    assert response.text == "Привет!"
    assert response.token_usage == 12
    assert response.provider == "openai"


async def test_openai_compat_raises_on_http_error():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(500, json={"error": "x"})
    )
    provider = OpenAICompatProvider(
        "https://example.test/v1", "key", "model-x", transport=transport
    )
    with pytest.raises(httpx.HTTPStatusError):
        await provider.generate(_request())
