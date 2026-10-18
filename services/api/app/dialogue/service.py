from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dialogue.context import build_context
from app.dialogue.generator import generate_draft
from app.dialogue.validator import validate_draft
from app.llm.gateway import LLMGateway
from app.models import CommunicationProfile, Conversation, Message, UserProfile


@dataclass(frozen=True)
class DraftOutcome:
    text: str
    provider: str
    model: str
    latency_ms: int
    ok: bool
    issues: list[str]


async def build_draft(
    session: AsyncSession, gateway: LLMGateway, conversation: Conversation
) -> DraftOutcome:
    user_profile = await session.scalar(
        select(UserProfile).where(UserProfile.user_id == conversation.user_id)
    )
    communication_profile = await session.scalar(
        select(CommunicationProfile).where(
            CommunicationProfile.user_id == conversation.user_id
        )
    )
    history_result = await session.scalars(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc())
    )
    context = build_context(user_profile, communication_profile, list(history_result))
    response = await generate_draft(gateway, context)
    validation = validate_draft(response.text, context.style)
    return DraftOutcome(
        text=response.text,
        provider=response.provider,
        model=response.model,
        latency_ms=response.latency_ms,
        ok=validation.ok,
        issues=validation.issues,
    )
