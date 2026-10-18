from app.llm.base import LLMRequest, LLMResponse


class EchoProvider:
    name = "echo"
    model = "echo"

    async def generate(self, request: LLMRequest) -> LLMResponse:
        last = request.messages[-1].content if request.messages else ""
        text = f"Эхо: {last}".strip()
        return LLMResponse(text=text, provider=self.name, model=self.model, latency_ms=0)
