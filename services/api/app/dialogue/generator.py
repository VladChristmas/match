from app.config import get_settings
from app.dialogue.context import DialogueContext
from app.llm.base import LLMRequest, LLMResponse
from app.llm.gateway import LLMGateway


async def generate_draft(gateway: LLMGateway, context: DialogueContext) -> LLMResponse:
    settings = get_settings()
    request = LLMRequest(
        task_type="dialogue_draft",
        system_prompt=context.system_prompt,
        messages=context.messages,
        max_tokens=settings.llm_max_tokens,
        temperature=settings.llm_temperature,
    )
    return await gateway.generate(request)
