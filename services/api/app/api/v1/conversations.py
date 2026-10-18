import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, GatewayDep, SessionDep
from app.config import get_settings
from app.dialogue.service import build_draft
from app.llm.gateway import LLMUnavailable
from app.llm.limits import count_user_runs, is_limit_reached
from app.models import Conversation, Message, ModelRun, User
from app.schemas import (
    ConversationCreate,
    ConversationRead,
    DraftRead,
    MessageImport,
    MessageRead,
)

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


async def _get_conversation(
    session: SessionDep, user: User, conversation_id: uuid.UUID
) -> Conversation:
    conversation = await session.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
    )
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return conversation


@router.post("", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreate, session: SessionDep, user: CurrentUser
) -> Conversation:
    conversation = Conversation(
        user_id=user.id,
        match_id=payload.match_id,
        last_activity_at=datetime.now(UTC),
    )
    if payload.autonomy_mode is not None:
        conversation.autonomy_mode = payload.autonomy_mode
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


@router.get("", response_model=list[ConversationRead])
async def list_conversations(
    session: SessionDep,
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[Conversation]:
    result = await session.scalars(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result)


@router.get("/{conversation_id}", response_model=ConversationRead)
async def read_conversation(
    conversation_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> Conversation:
    return await _get_conversation(session, user, conversation_id)


@router.get("/{conversation_id}/messages", response_model=list[MessageRead])
async def list_messages(
    conversation_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[Message]:
    conversation = await _get_conversation(session, user, conversation_id)
    result = await session.scalars(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc())
        .limit(limit)
        .offset(offset)
    )
    return list(result)


@router.post(
    "/{conversation_id}/messages/import",
    response_model=MessageRead,
    status_code=status.HTTP_201_CREATED,
)
async def import_message(
    conversation_id: uuid.UUID,
    payload: MessageImport,
    session: SessionDep,
    user: CurrentUser,
) -> Message:
    conversation = await _get_conversation(session, user, conversation_id)
    message = Message(
        conversation_id=conversation.id,
        direction=payload.direction,
        content=payload.content,
        external_message_id=payload.external_message_id,
        source=payload.source,
    )
    session.add(message)
    conversation.last_activity_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(message)
    return message


@router.post("/{conversation_id}/drafts", response_model=DraftRead)
async def create_draft(
    conversation_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    gateway: GatewayDep,
) -> DraftRead:
    conversation = await _get_conversation(session, user, conversation_id)
    settings = get_settings()
    used = await count_user_runs(session, user.id)
    if is_limit_reached(used, settings.llm_user_request_limit):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="LLM request limit reached",
        )
    try:
        outcome = await build_draft(session, gateway, conversation)
    except LLMUnavailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No LLM provider available",
        ) from None
    session.add(
        ModelRun(
            user_id=user.id,
            task_type="dialogue_draft",
            provider=outcome.provider,
            model=outcome.model,
            model_version=outcome.model,
            prompt_version="dialogue-draft-v1",
            latency_ms=outcome.latency_ms,
            token_usage=outcome.token_usage,
            status="ok",
        )
    )
    await session.commit()
    return DraftRead(
        text=outcome.text,
        provider=outcome.provider,
        model=outcome.model,
        latency_ms=outcome.latency_ms,
        validation_ok=outcome.ok,
        issues=outcome.issues,
    )
