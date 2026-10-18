from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class VisionRequest:
    image_base64: str
    instruction: str
    media_type: str = "image/png"
    max_tokens: int = 512
    temperature: float = 0.2


@dataclass(frozen=True)
class VisionResponse:
    text: str
    provider: str
    model: str
    latency_ms: int
    token_usage: int | None = None


class VisionProvider(Protocol):
    name: str
    model: str

    async def analyze(self, request: VisionRequest) -> VisionResponse: ...
