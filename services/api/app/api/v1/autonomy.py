"""Адаптивная автономность API (Этап 26, ADR-0032).

GET|PATCH /api/v1/autonomy/budget — бюджет автономности пользователя.
GET /api/v1/autonomy/errors — журнал ошибок автономности.
POST /api/v1/autonomy/reset-errors — сброс счётчика ошибок вручную.
GET|POST /api/v1/autonomy/calibration-rules — правила калибровки.
POST /api/v1/feedback/{feedback_id}/classify — классификация и калибровка отзыва.
"""

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.autonomy import (
    classify_and_calibrate,
    get_or_create_budget,
    list_calibration_rules,
    list_errors,
    reset_errors,
    update_budget,
)
from app.models import AutonomyBudget, AutonomyErrorLog, CalibrationRule, UserFeedback
from app.schemas import (
    AutonomyBudgetRead,
    AutonomyBudgetUpdate,
    AutonomyErrorLogRead,
    CalibrationRuleRead,
    CalibrationRuleUpdate,
    FeedbackClassificationRead,
    FeedbackClassifyRequest,
)

router = APIRouter(prefix="/api/v1/autonomy", tags=["autonomy"])


@router.get("/budget", response_model=AutonomyBudgetRead)
async def read_budget(session: SessionDep, user: CurrentUser) -> AutonomyBudget:
    budget = await get_or_create_budget(session, user)
    return budget


@router.patch("/budget", response_model=AutonomyBudgetRead)
async def update_budget_endpoint(
    payload: AutonomyBudgetUpdate, session: SessionDep, user: CurrentUser
) -> AutonomyBudget:
    budget = await update_budget(
        session,
        user,
        max_messages_per_day=payload.max_messages_per_day,
        active_start_hour=payload.active_start_hour,
        active_end_hour=payload.active_end_hour,
        allowed_conversation_ids=payload.allowed_conversation_ids,
        actions_always_confirm=payload.actions_always_confirm,
        auto_stop_after_errors=payload.auto_stop_after_errors,
        global_paused=payload.global_paused,
    )
    await session.commit()
    await session.refresh(budget)
    return budget


@router.get("/errors", response_model=list[AutonomyErrorLogRead])
async def get_errors(
    session: SessionDep,
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AutonomyErrorLog]:
    return await list_errors(session, user_id=user.id, limit=limit, offset=offset)


@router.post("/reset-errors", response_model=AutonomyBudgetRead)
async def reset_errors_endpoint(session: SessionDep, user: CurrentUser) -> AutonomyBudget:
    await reset_errors(session, user)
    await session.commit()
    budget = await get_or_create_budget(session, user)
    return budget


@router.get("/calibration-rules", response_model=list[CalibrationRuleRead])
async def get_calibration_rules(
    session: SessionDep,
    user: CurrentUser,
    rule_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[CalibrationRule]:
    return await list_calibration_rules(
        session, user_id=user.id, rule_type=rule_type, limit=limit, offset=offset
    )


@router.patch("/calibration-rules/{rule_id}", response_model=CalibrationRuleRead)
async def update_calibration_rule(
    rule_id: uuid.UUID,
    payload: CalibrationRuleUpdate,
    session: SessionDep,
    user: CurrentUser,
) -> CalibrationRule:
    rule = await session.scalar(
        select(CalibrationRule).where(
            CalibrationRule.id == rule_id, CalibrationRule.user_id == user.id
        )
    )
    if rule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Calibration rule not found"
        )
    if payload.confidence is not None:
        rule.confidence = payload.confidence
    if payload.action is not None:
        rule.action = dict(payload.action)
    if payload.condition is not None:
        rule.condition = dict(payload.condition)
    await session.flush()
    await session.refresh(rule)
    return rule


@router.post("/feedback/{feedback_id}/classify", response_model=FeedbackClassificationRead)
async def classify_feedback_endpoint(
    feedback_id: uuid.UUID,
    payload: FeedbackClassifyRequest,
    session: SessionDep,
    user: CurrentUser,
) -> FeedbackClassificationRead:
    feedback = await session.scalar(
        select(UserFeedback).where(UserFeedback.id == feedback_id, UserFeedback.user_id == user.id)
    )
    if feedback is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")
    classification, rule = await classify_and_calibrate(session, user, feedback)
    await session.commit()
    return FeedbackClassificationRead(
        feedback_id=feedback_id,
        classification=classification,
        rule_created=rule is not None,
        rule_id=rule.id if rule else None,
    )
