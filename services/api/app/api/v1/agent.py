import uuid
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Query, Response, status
from sqlalchemy import select

from app.agent.service import (
    PENDING,
    approve_action,
    enqueue_action,
    get_or_create_settings,
    reject_action,
)
from app.api.deps import CurrentUser, GatewayDep, SessionDep
from app.llm.gateway import LLMUnavailable
from app.models import AgentAction, Conversation, User
from app.schemas import AgentActionCreate, AgentActionRead, AgentSettingsRead, AgentSettingsUpdate

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


async def _user_conversation(
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


async def _user_action(
    session: SessionDep, user: User, action_id: uuid.UUID
) -> AgentAction:
    action = await session.scalar(
        select(AgentAction).where(
            AgentAction.id == action_id,
            AgentAction.user_id == user.id,
        )
    )
    if action is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action not found",
        )
    return action


@router.get("/settings", response_model=AgentSettingsRead)
async def read_settings(session: SessionDep, user: CurrentUser) -> AgentSettingsRead:
    settings = await get_or_create_settings(session, user)
    return settings


@router.patch("/settings", response_model=AgentSettingsRead)
async def update_settings(
    payload: AgentSettingsUpdate, session: SessionDep, user: CurrentUser
) -> AgentSettingsRead:
    settings = await get_or_create_settings(session, user)
    if payload.default_autonomy_mode is not None:
        settings.default_autonomy_mode = payload.default_autonomy_mode
    if payload.queue_paused is not None:
        settings.queue_paused = payload.queue_paused
    await session.commit()
    await session.refresh(settings)
    return settings


@router.post("/pause", response_model=AgentSettingsRead)
async def pause(session: SessionDep, user: CurrentUser) -> AgentSettingsRead:
    settings = await get_or_create_settings(session, user)
    settings.queue_paused = True
    await session.commit()
    await session.refresh(settings)
    return settings


@router.post("/resume", response_model=AgentSettingsRead)
async def resume(session: SessionDep, user: CurrentUser) -> AgentSettingsRead:
    settings = await get_or_create_settings(session, user)
    settings.queue_paused = False
    await session.commit()
    await session.refresh(settings)
    return settings


@router.get("/actions", response_model=list[AgentActionRead])
async def list_actions(
    session: SessionDep,
    user: CurrentUser,
    action_status: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AgentAction]:
    query = select(AgentAction).where(AgentAction.user_id == user.id)
    if action_status is not None:
        query = query.where(AgentAction.status == action_status)
    result = await session.scalars(
        query.order_by(AgentAction.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result)


@router.post("/actions", response_model=AgentActionRead)
async def create_action(
    payload: AgentActionCreate,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    gateway: GatewayDep,
    idempotency_key: Annotated[str | None, Header()] = None,
) -> AgentAction:
    if payload.text is None and not payload.generate:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide text or enable generate",
        )
    conversation = await _user_conversation(session, user, payload.conversation_id)
    try:
        action, created = await enqueue_action(
            session,
            gateway,
            user,
            conversation,
            text=payload.text,
            generate=payload.generate,
            idempotency_key=idempotency_key,
        )
    except LLMUnavailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No LLM provider available",
        ) from None
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return action


@router.post("/actions/{action_id}/approve", response_model=AgentActionRead)
async def approve(
    action_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> AgentAction:
    action = await _user_action(session, user, action_id)
    if action.status != PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending actions can be approved",
        )
    await approve_action(session, action)
    return action


@router.post("/actions/{action_id}/reject", response_model=AgentActionRead)
async def reject(
    action_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> AgentAction:
    action = await _user_action(session, user, action_id)
    if action.status != PENDING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending actions can be rejected",
        )
    await reject_action(session, action)
    return action
