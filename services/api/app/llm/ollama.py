import time

import httpx

from app.llm.base import LLMRequest, LLMResponse


class OllamaProvider:
    name = "ollama"

    def __init__(self, base_url: str, model: str, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def generate(self, request: LLMRequest) -> LLMResponse:
        payload = {
            "model": self.model,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
            "messages": [
                {"role": "system", "content": request.system_prompt},
                *({"role": m.role, "content": m.content} for m in request.messages),
            ],
        }
        started = time.perf_counter()
        async with httpx.AsyncClient(
            base_url=self.base_url, timeout=self.timeout
        ) as client:
            response = await client.post("/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
        latency_ms = int((time.perf_counter() - started) * 1000)
        return LLMResponse(
            text=data.get("message", {}).get("content", ""),
            provider=self.name,
            model=self.model,
            latency_ms=latency_ms,
            token_usage=data.get("eval_count"),
        )
