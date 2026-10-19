"""Автономность: настройки агента и очередь действий (Этап 8).

Модель очереди — таблица `agent_actions` со статусами. `auto_send` (ADR-0009) доставляет
сообщение сразу; иные режимы и общая пауза переводят действие в `pending`, где решение
принимает человек (`approve` / `reject`). Идемпотентность — по ключу `idempotency_key`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.autonomy import ERROR_REJECTED, check_execution_budget, record_error, record_success
from app.decision import STOP, build_state, decide, persist_decision
from app.dialogue.service import build_draft
from app.llm.gateway import LLMGateway
from app.models import AgentAction, AgentSettings, Conversation, Message, User

AUTO_SEND = "auto_send"
PENDING = "pending"
SCHEDULED = "scheduled"
SENT = "sent"
REJECTED = "rejected"
FAILED = "failed"


async def get_or_create_settings(session: AsyncSession, user: User) -> AgentSettings:
    settings = await session.scalar(select(AgentSettings).where(AgentSettings.user_id == user.id))
    if settings is None:
        settings = AgentSettings(user_id=user.id)
        session.add(settings)
        await session.commit()
        await session.refresh(settings)
    return settings


def should_auto_send(settings: AgentSettings, conversation: Conversation) -> bool:
    if settings.queue_paused:
        return False
    return conversation.autonomy_mode == AUTO_SEND


async def _deliver(
    session: AsyncSession,
    user: User,
    conversation: Conversation,
    action: AgentAction,
) -> None:
    message = Message(
        conversation_id=conversation.id,
        direction="outbound",
        content=action.text,
        source="agent",
        processing_status="sent",
    )
    session.add(message)
    conversation.last_activity_at = datetime.now(UTC)
    action.status = SENT
    action.sent_at = datetime.now(UTC)
    action.attempts = (action.attempts or 0) + 1
    await record_success(session, user)


async def enqueue_action(
    session: AsyncSession,
    gateway: LLMGateway,
    user: User,
    conversation: Conversation,
    *,
    text: str | None,
    generate: bool,
    idempotency_key: str | None,
    delay_seconds: int = 0,
) -> tuple[AgentAction, bool]:
    if idempotency_key:
        existing = await session.scalar(
            select(AgentAction).where(
                AgentAction.user_id == user.id,
                AgentAction.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return existing, False

    settings = await get_or_create_settings(session, user)

    state = await build_state(session, user, conversation, trigger_text=text)
    decision = decide(state, trigger_text=text)

    action = AgentAction(
        user_id=user.id,
        conversation_id=conversation.id,
        idempotency_key=idempotency_key,
        attempts=0,
    )
    if text is not None:
        action.text = text
    elif generate:
        outcome = await build_draft(session, gateway, conversation)
        action.text = outcome.text
        action.provider = outcome.provider
        action.model = outcome.model
        action.validation_ok = outcome.ok

    if decision.mode == STOP:
        action.status = PENDING
    elif should_auto_send(settings, conversation) and decision.allowed_autonomously:
        budget_allowed, budget_reason, _budget_mode = await check_execution_budget(
            session, user, conversation
        )
        if budget_allowed:
            if delay_seconds > 0:
                action.status = SCHEDULED
                action.scheduled_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)
                action.next_attempt_at = action.scheduled_at
            else:
                await _deliver(session, user, conversation, action)
        else:
            action.status = PENDING
    else:
        action.status = PENDING

    session.add(action)
    await session.flush()
    persist_decision(
        session,
        user_id=user.id,
        conversation_id=conversation.id,
        decision=decision,
        action_id=action.id,
    )
    await session.commit()
    await session.refresh(action)
    return action, True


async def approve_action(session: AsyncSession, user: User, action: AgentAction) -> None:
    conversation = await session.get(Conversation, action.conversation_id)
    if conversation is None:
        raise ValueError("Conversation not found")
    await _deliver(session, user, conversation, action)
    action.decided_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(action)


async def reject_action(session: AsyncSession, user: User, action: AgentAction) -> None:
    action.status = REJECTED
    action.decided_at = datetime.now(UTC)
    await record_error(
        session,
        user,
        conversation_id=action.conversation_id,
        action_id=action.id,
        error_type=ERROR_REJECTED,
    )
    await session.commit()
    await session.refresh(action)
