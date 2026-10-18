import time

import httpx

from app.vision.base import VisionRequest, VisionResponse


class OllamaVisionProvider:
    """Локальный анализ кадров через Ollama (мультимодальная модель).

    Изображение передаётся в поле `images` (base64 без data-URL), как ожидает
    `/api/chat`. По умолчанию это локальный провайдер: кадр не покидает машину.
    """

    name = "ollama"

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._transport = transport

    async def analyze(self, request: VisionRequest) -> VisionResponse:
        payload = {
            "model": self.model,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
            "messages": [
                {"role": "user", "content": request.instruction, "images": [request.image_base64]},
            ],
        }
        started = time.perf_counter()
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            transport=self._transport,
        ) as client:
            response = await client.post("/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()
        latency_ms = int((time.perf_counter() - started) * 1000)
        return VisionResponse(
            text=data.get("message", {}).get("content", ""),
            provider=self.name,
            model=self.model,
            latency_ms=latency_ms,
            token_usage=data.get("eval_count"),
        )


class OpenAICompatVisionProvider:
    """Анализ кадров через OpenAI-совместимый API (облако).

    Включается только при явной настройке (`MATCH_VISION_PROVIDER=openai` и ключ);
    так кадры не уходят в облако по умолчанию.
    """

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

    async def analyze(self, request: VisionRequest) -> VisionResponse:
        payload = {
            "model": self.model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": request.instruction},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{request.media_type};base64,{request.image_base64}"
                            },
                        },
                    ],
                }
            ],
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        started = time.perf_counter()
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            transport=self._transport,
        ) as client:
            response = await client.post("/chat/completions", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        latency_ms = int((time.perf_counter() - started) * 1000)
        choices = data.get("choices") or []
        text = choices[0].get("message", {}).get("content", "") if choices else ""
        token_usage = data.get("usage", {}).get("total_tokens")
        return VisionResponse(
            text=text,
            provider=self.name,
            model=self.model,
            latency_ms=latency_ms,
            token_usage=token_usage,
        )
