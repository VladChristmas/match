"""Сохранение решений Decision Loop (Этап 23, ADR-0029).

Решение материализуется в `agent_decisions`, чтобы для значимого действия можно было
восстановить основания (прозрачность, раздел 10 спецификации).
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.decision.policy import Decision
from app.models import AgentDecision


def persist_decision(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    decision: Decision,
    action_id: uuid.UUID | None = None,
) -> AgentDecision:
    """Создаёт запись решения (без коммита — коммитит вызывающий код)."""
    record = AgentDecision(
        user_id=user_id,
        conversation_id=conversation_id,
        action_id=action_id,
        action=decision.action,
        mode=decision.mode,
        rationale=decision.rationale,
        confidence=decision.confidence,
        alternatives=list(decision.alternatives),
        evidence=list(decision.evidence),
        escalation_reason=decision.escalation_reason,
        missing=list(decision.missing),
    )
    session.add(record)
    return record


__all__ = ["Decision", "persist_decision"]
