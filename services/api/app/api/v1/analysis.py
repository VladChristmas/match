import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, SessionDep
from app.compatibility.engine import (
    CounterpartProfile,
    assess_compatibility,
    reciprocity_from_counts,
)
from app.models import (
    CompatibilityAssessment,
    Conversation,
    Message,
    RiskAssessment,
    User,
    UserProfile,
)
from app.schemas import (
    CompatibilityRead,
    CompatibilityRequest,
    RiskRead,
    RiskRequest,
)
from app.trust.engine import assess_risk

router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])


async def _resolve_conversation(
    session: SessionDep, user: User, conversation_id: uuid.UUID | None
) -> Conversation | None:
    if conversation_id is None:
        return None
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


async def _direction_counts(session: SessionDep, conversation_id: uuid.UUID) -> dict[str, int]:
    rows = await session.execute(
        select(Message.direction, func.count())
        .where(Message.conversation_id == conversation_id)
        .group_by(Message.direction)
    )
    counts = {direction: count for direction, count in rows.all()}
    return {"inbound": counts.get("inbound", 0), "outbound": counts.get("outbound", 0)}


@router.post(
    "/compatibility",
    response_model=CompatibilityRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_compatibility_assessment(
    payload: CompatibilityRequest, session: SessionDep, user: CurrentUser
) -> CompatibilityAssessment:
    conversation = await _resolve_conversation(session, user, payload.conversation_id)
    user_profile = await session.scalar(
        select(UserProfile).where(UserProfile.user_id == user.id)
    )
    reciprocity = payload.reciprocity
    if reciprocity is None and conversation is not None:
        counts = await _direction_counts(session, conversation.id)
        reciprocity = reciprocity_from_counts(counts["inbound"], counts["outbound"])
    result = assess_compatibility(
        list(user_profile.relationship_goals) if user_profile else [],
        list(user_profile.values) if user_profile else [],
        dict(user_profile.preferences) if user_profile else {},
        CounterpartProfile(
            goals=payload.counterpart.goals,
            values=payload.counterpart.values,
            lifestyle=payload.counterpart.lifestyle,
        ),
        reciprocity,
    )
    assessment = CompatibilityAssessment(
        user_id=user.id,
        match_id=payload.match_id or (conversation.match_id if conversation else None),
        conversation_id=conversation.id if conversation else None,
        goals_alignment=result.goals_alignment,
        values_alignment=result.values_alignment,
        lifestyle_alignment=result.lifestyle_alignment,
        reciprocity=result.reciprocity,
        uncertainty=result.uncertainty,
        explanation=result.explanation,
    )
    session.add(assessment)
    await session.commit()
    await session.refresh(assessment)
    return assessment


@router.get("/compatibility", response_model=list[CompatibilityRead])
async def list_compatibility_assessments(
    session: SessionDep,
    user: CurrentUser,
    conversation_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[CompatibilityAssessment]:
    statement = select(CompatibilityAssessment).where(
        CompatibilityAssessment.user_id == user.id
    )
    if conversation_id is not None:
        statement = statement.where(
            CompatibilityAssessment.conversation_id == conversation_id
        )
    result = await session.scalars(
        statement.order_by(CompatibilityAssessment.assessed_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result)


@router.post("/risk", response_model=RiskRead, status_code=status.HTTP_201_CREATED)
async def create_risk_assessment(
    payload: RiskRequest, session: SessionDep, user: CurrentUser
) -> RiskAssessment:
    conversation = await _resolve_conversation(session, user, payload.conversation_id)
    messages = list(payload.messages)
    if conversation is not None:
        contents = await session.scalars(
            select(Message.content).where(
                Message.conversation_id == conversation.id,
                Message.direction == "inbound",
                Message.content.is_not(None),
            )
        )
        messages.extend(content for content in contents if content)
    outcome = assess_risk(messages)
    assessment = RiskAssessment(
        user_id=user.id,
        match_id=payload.match_id or (conversation.match_id if conversation else None),
        conversation_id=conversation.id if conversation else None,
        risk_category=outcome.risk_category,
        signals=[
            {"category": signal.category, "matches": signal.matches}
            for signal in outcome.signals
        ],
        confidence=outcome.confidence,
        explanation=outcome.explanation,
        recommended_action=outcome.recommended_action,
    )
    session.add(assessment)
    await session.commit()
    await session.refresh(assessment)
    return assessment


@router.get("/risk", response_model=list[RiskRead])
async def list_risk_assessments(
    session: SessionDep,
    user: CurrentUser,
    conversation_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[RiskAssessment]:
    statement = select(RiskAssessment).where(RiskAssessment.user_id == user.id)
    if conversation_id is not None:
        statement = statement.where(RiskAssessment.conversation_id == conversation_id)
    result = await session.scalars(
        statement.order_by(RiskAssessment.assessed_at.desc()).limit(limit).offset(offset)
    )
    return list(result)
