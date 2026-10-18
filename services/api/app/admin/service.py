"""Админ-кабинет (Этап 15, OQ-3): роль `admin` и агрегированные метрики.

Метрики не содержат персональных данных: только количества по категориям
(пользователи, диалоги, сообщения, запуски моделей, наблюдения vision, действия агента,
отзывы, токены) и сводка несекретных настроек. Персональный профиль и тексты сообщений
недоступны даже суперадмину (ADR-0007).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import (
    AccessToken,
    AgentAction,
    Conversation,
    Message,
    ModelRun,
    User,
    UserFeedback,
    VisionObservation,
)

UNKNOWN_KEY = "unknown"


async def _total(session: AsyncSession, model) -> int:
    return int(await session.scalar(select(func.count()).select_from(model)) or 0)


async def _by_key(session: AsyncSession, column) -> dict[str, int]:
    rows = (await session.execute(select(column, func.count()).group_by(column))).all()
    return {(UNKNOWN_KEY if key is None else str(key)): int(count) for key, count in rows}


async def _metric(session: AsyncSession, model, column) -> dict:
    return {"total": await _total(session, model), "by_key": await _by_key(session, column)}


async def maybe_promote_admin(session: AsyncSession, user: User) -> User:
    """Выдаёт роль `admin`, если `token_ref` перечислен в `MATCH_ADMIN_TOKEN_REFS`."""
    if user.role == "admin":
        return user
    if user.token_ref in get_settings().admin_refs:
        user.role = "admin"
        await session.commit()
        await session.refresh(user)
    return user


def settings_summary() -> dict[str, str]:
    settings = get_settings()
    return {
        "environment": settings.environment,
        "llm_provider": settings.llm_provider,
        "vision_provider": settings.vision_provider,
        "rate_limit_backend": settings.rate_limit_backend,
        "rate_limit_per_minute": str(settings.rate_limit_per_minute),
        "auth_allow_legacy_tokens": str(settings.auth_allow_legacy_tokens).lower(),
        "admin_configured": str(bool(settings.admin_refs)).lower(),
    }


async def collect_metrics(session: AsyncSession) -> dict:
    active_tokens = int(
        await session.scalar(
            select(func.count()).select_from(AccessToken).where(AccessToken.revoked_at.is_(None))
        )
        or 0
    )
    tokens_total = await _total(session, AccessToken)

    return {
        "generated_at": datetime.now(UTC),
        "users": await _metric(session, User, User.role),
        "conversations": await _metric(session, Conversation, Conversation.status),
        "messages": await _metric(session, Message, Message.processing_status),
        "model_runs": await _metric(session, ModelRun, ModelRun.task_type),
        "model_runs_by_provider": await _metric(session, ModelRun, ModelRun.provider),
        "vision_observations": await _metric(
            session, VisionObservation, VisionObservation.provider
        ),
        "agent_actions": await _metric(session, AgentAction, AgentAction.status),
        "feedback": await _metric(session, UserFeedback, UserFeedback.feedback_type),
        "access_tokens": {
            "total": tokens_total,
            "by_key": {"active": active_tokens, "revoked": tokens_total - active_tokens},
        },
        "settings": settings_summary(),
    }
