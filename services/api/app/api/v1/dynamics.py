"""Динамика отношений API (Этап 25, ADR-0031).

GET /api/v1/dynamics/signals — временные ряды сигналов по измерению.
GET /api/v1/dynamics/timeline — поворотные моменты familiar.
POST /api/v1/dynamics/compute — пересчитать сигналы для разговора.
GET /api/v1/dynamics/compare — сравнить два периода.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.dynamics import (
    DIMENSIONS,
    compute_signals,
    detect_significant_change,
    list_signals,
    list_timeline,
    record_turning_point,
)
from app.models import Conversation, RelationshipSignal, RelationshipTimeline
from app.schemas import RelationshipSignalRead, RelationshipTimelineRead

router = APIRouter(prefix="/api/v1/dynamics", tags=["dynamics"])


async def _user_conversation(
    session: SessionDep, user: CurrentUser, conversation_id: uuid.UUID
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


@router.get("/signals", response_model=list[RelationshipSignalRead])
async def get_signals(
    session: SessionDep,
    user: CurrentUser,
    conversation_id: Annotated[uuid.UUID | None, Query()] = None,
    dimension: Annotated[str | None, Query()] = None,
    since_days: Annotated[int, Query(ge=1, le=365)] = 90,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: int = Query(default=0, ge=0),
) -> list[RelationshipSignal]:
    if dimension is not None and dimension not in DIMENSIONS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"unknown dimension: {dimension}",
        )
    since = datetime.now(UTC) - timedelta(days=since_days)
    return await list_signals(
        session,
        user_id=user.id,
        conversation_id=conversation_id,
        dimension=dimension,
        since=since,
        limit=limit,
        offset=offset,
    )


@router.post("/signals/compute", response_model=list[RelationshipSignalRead])
async def compute_conversation_signals(
    conversation_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> list[RelationshipSignal]:
    conversation = await _user_conversation(session, user, conversation_id)
    signals = await compute_signals(session, user.id, conversation)
    await session.commit()
    return signals


@router.get("/timeline", response_model=list[RelationshipTimelineRead])
async def get_timeline(
    session: SessionDep,
    user: CurrentUser,
    conversation_id: Annotated[uuid.UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: int = Query(default=0, ge=0),
) -> list[RelationshipTimeline]:
    return await list_timeline(
        session,
        user_id=user.id,
        conversation_id=conversation_id,
        limit=limit,
        offset=offset,
    )


@router.get("/compare", response_model=list[dict])
async def compare_periods(
    session: SessionDep,
    user: CurrentUser,
    conversation_id: uuid.UUID,
    days: Annotated[int, Query(ge=1, le=90)] = 30,
) -> list[dict]:
    await _user_conversation(session, user, conversation_id)
    now = datetime.now(UTC)
    current_start = now - timedelta(days=days)
    previous_start = now - timedelta(days=days * 2)

    current = await list_signals(
        session,
        user_id=user.id,
        conversation_id=conversation_id,
        since=current_start,
        limit=1000,
        offset=0,
    )
    previous = await list_signals(
        session,
        user_id=user.id,
        conversation_id=conversation_id,
        since=previous_start,
        until=current_start,
        limit=1000,
        offset=0,
    )
    return detect_significant_change(previous, current)


@router.post("/timeline", response_model=RelationshipTimelineRead)
async def add_turning_point(
    conversation_id: uuid.UUID,
    event_type: str,
    description: str,
    session: SessionDep,
    user: CurrentUser,
) -> RelationshipTimeline:
    await _user_conversation(session, user, conversation_id)
    current = await list_signals(
        session,
        user_id=user.id,
        conversation_id=conversation_id,
        limit=100,
        offset=0,
    )
    timeline = await record_turning_point(
        session,
        user_id=user.id,
        conversation_id=conversation_id,
        event_type=event_type,
        description=description,
        signals_before=[{"dimension": s.dimension, "value": s.value} for s in current],
        signals_after=[{"dimension": s.dimension, "value": s.value} for s in current],
    )
    await session.commit()
    await session.refresh(timeline)
    return timeline
