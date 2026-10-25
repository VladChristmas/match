"""Динамика отношений (Этап 25, ADR-0031).

Анализирует траекторию отношений во времени, а не отдельные сообщения.
Вычисляет сигналы по шести независимым измерениям и фиксирует поворотные моменты.
Не сворачивает измерения в один «магический балл».
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    CompatibilityAssessment,
    Conversation,
    Message,
    RelationshipSignal,
    RelationshipTimeline,
    UserProfile,
)
from app.trust.engine import assess_risk

RECIPROCITY = "reciprocity"
CONSISTENCY = "consistency"
EMOTIONAL_COMFORT = "emotional_comfort"
EXPECTATION_ALIGNMENT = "expectation_alignment"
AGREEMENT_ABILITY = "agreement_ability"
RELATIONSHIP_DEVELOPMENT = "relationship_development"

DIMENSIONS = (
    RECIPROCITY,
    CONSISTENCY,
    EMOTIONAL_COMFORT,
    EXPECTATION_ALIGNMENT,
    AGREEMENT_ABILITY,
    RELATIONSHIP_DEVELOPMENT,
)

SIGNAL_WINDOW_DAYS = 90
MIN_OBSERVATIONS_PER_DIMENSION = 5


def _jaccard(first: list[str], second: list[str]) -> float:
    set_a = {item.strip().lower() for item in first if item and item.strip()}
    set_b = {item.strip().lower() for item in second if item and item.strip()}
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


def _round2(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 2)


def _as_utc(value: datetime | None) -> datetime | None:
    """Приводит момент к offset-aware UTC.

    PostgreSQL (`timestamptz`) возвращает aware-даты, SQLite — наивные.
    Без нормализации сравнение окна с датой сообщения падает на PostgreSQL
    (`TypeError: can't compare offset-naive and offset-aware datetimes`),
    поэтому каждая дата приводится к UTC перед сравнениями в Python.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _reciprocity_from_messages(messages: list[Message]) -> float:
    inbound = sum(1 for m in messages if m.direction == "inbound")
    outbound = sum(1 for m in messages if m.direction == "outbound")
    total = inbound + outbound
    if total == 0:
        return 0.5
    return _round2(1 - abs(inbound - outbound) / total)


async def compute_signals(
    session: AsyncSession,
    user_id,
    conversation: Conversation,
    now: datetime | None = None,
) -> list[RelationshipSignal]:
    """Вычисляет сигналы по всем измерениям для разговора на момент `now`."""
    moment = _as_utc(now) or datetime.now(UTC)
    window_start = moment - timedelta(days=SIGNAL_WINDOW_DAYS)

    messages = list(
        await session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.asc())
        )
    )
    window_messages = [
        m for m in messages if (_as_utc(m.created_at) or window_start) >= window_start
    ]

    profile = await session.scalar(select(UserProfile).where(UserProfile.user_id == user_id))
    list(profile.relationship_goals) if profile else []
    list(profile.values) if profile else []
    dict(profile.preferences) if profile else {}

    risk = assess_risk([m.content for m in window_messages if m.content])
    emotional_comfort = _round2(1.0 - risk.confidence)

    compatibility: CompatibilityAssessment | None = await session.scalar(
        select(CompatibilityAssessment)
        .where(CompatibilityAssessment.conversation_id == conversation.id)
        .order_by(CompatibilityAssessment.assessed_at.desc())
        .limit(1)
    )

    signals: list[RelationshipSignal] = []

    # 1. Взаимность — баланс входящих/исходящих сообщений в окне.
    window_inbound = sum(1 for m in window_messages if m.direction == "inbound")
    window_outbound = sum(1 for m in window_messages if m.direction == "outbound")
    reciprocity = _reciprocity_from_messages(window_messages)
    signals.append(
        RelationshipSignal(
            user_id=user_id,
            conversation_id=conversation.id,
            dimension=RECIPROCITY,
            value=reciprocity,
            evidence=[
                {
                    "kind": "history",
                    "inbound": window_inbound,
                    "outbound": window_outbound,
                }
            ],
            observed_at=moment,
        )
    )

    # 2. Последовательность — стабильность評価 compatiblity во времени.
    consistency = _round2(compatibility.uncertainty if compatibility else 0.5)
    signals.append(
        RelationshipSignal(
            user_id=user_id,
            conversation_id=conversation.id,
            dimension=CONSISTENCY,
            value=consistency,
            evidence=[
                {
                    "kind": "compatibility",
                    "id": str(compatibility.id) if compatibility else None,
                    "uncertainty": compatibility.uncertainty if compatibility else None,
                }
            ],
            observed_at=moment,
        )
    )

    # 3. Эмоциональный комфорт — инвертированный риск.
    signals.append(
        RelationshipSignal(
            user_id=user_id,
            conversation_id=conversation.id,
            dimension=EMOTIONAL_COMFORT,
            value=emotional_comfort,
            evidence=[
                {
                    "kind": "risk",
                    "category": risk.risk_category,
                    "confidence": risk.confidence,
                    "recommended_action": risk.recommended_action,
                }
            ],
            observed_at=moment,
        )
    )

    # 4. Совместимость ожиданий — среднее по целям/ценностям/образу жизни.
    if compatibility:
        expectation_alignment = _round2(
            (
                compatibility.goals_alignment
                + compatibility.values_alignment
                + compatibility.lifestyle_alignment
            )
            / 3
        )
    else:
        expectation_alignment = 0.5
    signals.append(
        RelationshipSignal(
            user_id=user_id,
            conversation_id=conversation.id,
            dimension=EXPECTATION_ALIGNMENT,
            value=expectation_alignment,
            evidence=[
                {
                    "kind": "compatibility",
                    "id": str(compatibility.id) if compatibility else None,
                    "goals": compatibility.goals_alignment if compatibility else None,
                    "values": compatibility.values_alignment if compatibility else None,
                    "lifestyle": compatibility.lifestyle_alignment if compatibility else None,
                }
            ],
            observed_at=moment,
        )
    )

    # 5. Способность договариваться — обратная неопределённость совместимости.
    agreement_ability = _round2(1.0 - (compatibility.uncertainty if compatibility else 0.5))
    signals.append(
        RelationshipSignal(
            user_id=user_id,
            conversation_id=conversation.id,
            dimension=AGREEMENT_ABILITY,
            value=agreement_ability,
            evidence=[
                {
                    "kind": "compatibility",
                    "id": str(compatibility.id) if compatibility else None,
                    "uncertainty": compatibility.uncertainty if compatibility else None,
                }
            ],
            observed_at=moment,
        )
    )

    # 6. Развитие знакомства — активность и углубление диалога во времени.
    total_messages = len(messages)
    window_count = len(window_messages)
    if total_messages == 0:
        development = 0.0
    else:
        recent_share = window_count / total_messages
        development = _round2(min(1.0, recent_share + reciprocity * 0.3))
    signals.append(
        RelationshipSignal(
            user_id=user_id,
            conversation_id=conversation.id,
            dimension=RELATIONSHIP_DEVELOPMENT,
            value=development,
            evidence=[
                {
                    "kind": "history",
                    "total_messages": total_messages,
                    "window_messages": window_count,
                    "recent_share": round(recent_share, 2) if total_messages else 0.0,
                }
            ],
            observed_at=moment,
        )
    )

    for signal in signals:
        session.add(signal)
    await session.flush()
    return signals


async def list_signals(
    session: AsyncSession,
    *,
    user_id,
    conversation_id=None,
    dimension: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> Sequence[RelationshipSignal]:
    query = select(RelationshipSignal).where(RelationshipSignal.user_id == user_id)
    if conversation_id is not None:
        query = query.where(RelationshipSignal.conversation_id == conversation_id)
    if dimension is not None:
        if dimension not in DIMENSIONS:
            raise ValueError(f"unknown dimension: {dimension}")
        query = query.where(RelationshipSignal.dimension == dimension)
    if since is not None:
        query = query.where(RelationshipSignal.observed_at >= since)
    if until is not None:
        query = query.where(RelationshipSignal.observed_at < until)
    result = await session.scalars(
        query.order_by(RelationshipSignal.observed_at.desc()).limit(limit).offset(offset)
    )
    return list(result)


async def record_turning_point(
    session: AsyncSession,
    *,
    user_id,
    conversation_id,
    event_type: str,
    description: str,
    signals_before: list[dict],
    signals_after: list[dict],
) -> RelationshipTimeline:
    timeline = RelationshipTimeline(
        user_id=user_id,
        conversation_id=conversation_id,
        event_type=event_type,
        description=description,
        signals_before=list(signals_before),
        signals_after=list(signals_after),
    )
    session.add(timeline)
    await session.flush()
    return timeline


async def list_timeline(
    session: AsyncSession,
    *,
    user_id,
    conversation_id=None,
    limit: int = 50,
    offset: int = 0,
) -> Sequence[RelationshipTimeline]:
    query = select(RelationshipTimeline).where(RelationshipTimeline.user_id == user_id)
    if conversation_id is not None:
        query = query.where(RelationshipTimeline.conversation_id == conversation_id)
    result = await session.scalars(
        query.order_by(RelationshipTimeline.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result)


def detect_significant_change(
    previous: list[RelationshipSignal],
    current: list[RelationshipSignal],
) -> list[dict]:
    """Сравнивает два набора сигналов и возвращает значимые изменения."""
    prev_by_dim = {s.dimension: s.value for s in previous}
    curr_by_dim = {s.dimension: s.value for s in current}
    changes: list[dict] = []
    for dimension in DIMENSIONS:
        prev = prev_by_dim.get(dimension)
        curr = curr_by_dim.get(dimension)
        if prev is None or curr is None:
            continue
        delta = round(curr - prev, 2)
        if abs(delta) >= 0.2:
            changes.append(
                {
                    "dimension": dimension,
                    "before": prev,
                    "after": curr,
                    "delta": delta,
                    "direction": "improved" if delta > 0 else "declined",
                }
            )
    return changes
