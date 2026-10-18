import time

import httpx

from app.llm.base import LLMRequest, LLMResponse


class OpenAICompatProvider:
    name = "openai"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self._transport = transport

    async def generate(self, request: LLMRequest) -> LLMResponse:
        payload = {
            "model": self.model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                *({"role": m.role, "content": m.content} for m in request.messages),
            ],
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        started = time.perf_counter()
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            transport=self._transport,
        ) as client:
            response = await client.post(
                "/chat/completions", json=payload, headers=headers
            )
            response.raise_for_status()
            data = response.json()
        latency_ms = int((time.perf_counter() - started) * 1000)
        choices = data.get("choices") or []
        text = choices[0].get("message", {}).get("content", "") if choices else ""
        token_usage = data.get("usage", {}).get("total_tokens")
        return LLMResponse(
            text=text,
            provider=self.name,
            model=self.model,
            latency_ms=latency_ms,
            token_usage=token_usage,
        )
