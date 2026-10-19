"""Модель состояния агента (Этап 23, ADR-0029).

Снимок `AgentState` собирается из уже существующих источников (профиль, стиль, настройки
автономности, сообщения, оценки `trust`/`compatibility`) в момент принятия решения и не
кэшируется между запросами. Слой ничего не хранит сам — он только читает.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.compatibility.engine import reciprocity_from_counts
from app.models import (
    AgentSettings,
    CommunicationProfile,
    CompatibilityAssessment,
    Conversation,
    Message,
    User,
    UserProfile,
)
from app.trust.engine import assess_risk

RECENT_MESSAGES_FOR_RISK = 10


@dataclass(frozen=True)
class AgentState:
    """Актуальный снимок для Decision Loop. Данные — только для чтения."""

    user_id: uuid.UUID
    conversation_id: uuid.UUID
    autonomy_mode: str
    queue_paused: bool
    goals: list[str] = field(default_factory=list)
    values: list[str] = field(default_factory=list)
    boundaries: dict[str, Any] = field(default_factory=dict)
    style: dict[str, Any] = field(default_factory=dict)
    risk_category: str = "none"
    risk_action: str = "none"
    risk_confidence: float = 0.0
    reciprocity: float = 0.5
    compatibility_uncertainty: float | None = None
    compatibility_assessment_id: uuid.UUID | None = None
    inbound_count: int = 0
    outbound_count: int = 0
    last_inbound_text: str | None = None
    missing: list[str] = field(default_factory=list)


async def build_state(
    session: AsyncSession,
    user: User,
    conversation: Conversation,
    trigger_text: str | None = None,
) -> AgentState:
    """Собирает `AgentState` из текущих данных. Отсутствующие данные попадают в `missing`.

    `trigger_text` — кандидат в исходящее сообщение: учитывается при оценке риска, чтобы
    стоп-фактор мог заблокировать отправку до того, как действие уйдёт (раздел 4 спецификации).
    """
    profile = await session.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
    communication = await session.scalar(
        select(CommunicationProfile).where(CommunicationProfile.user_id == user.id)
    )
    settings = await session.scalar(select(AgentSettings).where(AgentSettings.user_id == user.id))
    messages = list(
        await session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.asc())
        )
    )
    inbound = [m for m in messages if m.direction == "inbound"]
    outbound = [m for m in messages if m.direction == "outbound"]

    risk_texts = [m.content for m in messages if m.content][-RECENT_MESSAGES_FOR_RISK:]
    if trigger_text:
        risk_texts.append(trigger_text)
    risk = assess_risk(risk_texts)

    compatibility = await session.scalar(
        select(CompatibilityAssessment)
        .where(CompatibilityAssessment.conversation_id == conversation.id)
        .order_by(CompatibilityAssessment.assessed_at.desc())
        .limit(1)
    )

    missing: list[str] = []
    if profile is None:
        missing.append("profile")
    if profile is None or not profile.relationship_goals:
        missing.append("goals")
    if not communication:
        missing.append("communication_profile")

    return AgentState(
        user_id=user.id,
        conversation_id=conversation.id,
        autonomy_mode=conversation.autonomy_mode,
        queue_paused=bool(settings.queue_paused) if settings else False,
        goals=list(profile.relationship_goals) if profile else [],
        values=list(profile.values) if profile else [],
        boundaries=dict(profile.boundaries) if profile else {},
        style=dict(communication.style_preferences) if communication else {},
        risk_category=risk.risk_category,
        risk_action=risk.recommended_action,
        risk_confidence=risk.confidence,
        reciprocity=(reciprocity_from_counts(len(inbound), len(outbound)) if messages else 0.5),
        compatibility_uncertainty=compatibility.uncertainty if compatibility else None,
        compatibility_assessment_id=compatibility.id if compatibility else None,
        inbound_count=len(inbound),
        outbound_count=len(outbound),
        last_inbound_text=inbound[-1].content if inbound else None,
        missing=missing,
    )
