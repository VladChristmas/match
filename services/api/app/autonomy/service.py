"""Адаптивная автономность и калибровка (Этап 26, ADR-0032).

Бюджет автономности — пределы самостоятельной работы агента, проверяемые перед
автономной доставкой. Калибровка обратной связи — классификация отзывов
пользователя, выявление закономерностей и обновление правил поведения.
Ничто не расширяет права агента самовольно; уверенность модели ≠ разрешение.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AgentAction,
    AutonomyBudget,
    AutonomyErrorLog,
    CalibrationRule,
    Conversation,
    User,
    UserFeedback,
)

# Константы порогов (OQ-9/OQ-12, valeurs по умолчанию).
MAX_MESSAGES_PER_DAY_DEFAULT = 50
ACTIVE_START_HOUR_DEFAULT = 0
ACTIVE_END_HOUR_DEFAULT = 24
AUTO_STOP_AFTER_ERRORS_DEFAULT = 3
CONFIDENCE_AUTO_THRESHOLD = 0.70
UNCERTAINTY_VERIFY_THRESHOLD = 0.67
PATTERN_MIN_REPETITIONS = 3
CALIBRATION_CONFIDENCE_MIN = 0.5
CALIBRATION_CONFIDENCE_MAX = 0.95

ERROR_REJECTED = "rejected"
ERROR_EDITED = "edited"
ERROR_CANCELLED = "cancelled"
ERROR_BLOCKED = "blocked"

RULE_STYLE_PREFERENCE = "style_preference"
RULE_STRATEGY_RULE = "strategy_rule"
RULE_CONFIDENCE_ADJUSTMENT = "confidence_adjustment"

CLASS_FACTUAL_ERROR = "factual_error"
CLASS_WRONG_TONE = "wrong_tone"
CLASS_WRONG_STRATEGY = "wrong_strategy"
CLASS_PERSONAL_PREFERENCE = "personal_preference"

ERROR_TYPES = {ERROR_REJECTED, ERROR_EDITED, ERROR_CANCELLED, ERROR_BLOCKED}
RULE_TYPES = {RULE_STYLE_PREFERENCE, RULE_STRATEGY_RULE, RULE_CONFIDENCE_ADJUSTMENT}
CLASSIFICATIONS = {
    CLASS_FACTUAL_ERROR,
    CLASS_WRONG_TONE,
    CLASS_WRONG_STRATEGY,
    CLASS_PERSONAL_PREFERENCE,
}


def _validate_error_type(error_type: str) -> None:
    if error_type not in ERROR_TYPES:
        raise ValueError(f"unknown autonomy error type: {error_type}")


def _validate_rule_type(rule_type: str) -> None:
    if rule_type not in RULE_TYPES:
        raise ValueError(f"unknown calibration rule type: {rule_type}")


def _validate_classification(classification: str) -> None:
    if classification not in CLASSIFICATIONS:
        raise ValueError(f"unknown feedback classification: {classification}")


async def get_or_create_budget(session: AsyncSession, user: User) -> AutonomyBudget:
    budget = await session.scalar(select(AutonomyBudget).where(AutonomyBudget.user_id == user.id))
    if budget is None:
        budget = AutonomyBudget(user_id=user.id)
        session.add(budget)
        await session.flush()
        await session.refresh(budget)
    return budget


async def update_budget(
    session: AsyncSession,
    user: User,
    *,
    max_messages_per_day: int | None = None,
    active_start_hour: int | None = None,
    active_end_hour: int | None = None,
    allowed_conversation_ids: list | None = None,
    actions_always_confirm: list | None = None,
    auto_stop_after_errors: int | None = None,
    global_paused: bool | None = None,
) -> AutonomyBudget:
    budget = await get_or_create_budget(session, user)
    if max_messages_per_day is not None:
        budget.max_messages_per_day = max_messages_per_day
    if active_start_hour is not None:
        budget.active_start_hour = active_start_hour
    if active_end_hour is not None:
        budget.active_end_hour = active_end_hour
    if allowed_conversation_ids is not None:
        budget.allowed_conversation_ids = list(allowed_conversation_ids)
    if actions_always_confirm is not None:
        budget.actions_always_confirm = list(actions_always_confirm)
    if auto_stop_after_errors is not None:
        budget.auto_stop_after_errors = auto_stop_after_errors
    if global_paused is not None:
        budget.global_paused = bool(global_paused)
    await session.flush()
    await session.refresh(budget)
    return budget


async def check_execution_budget(
    session: AsyncSession,
    user: User,
    conversation: Conversation,
) -> tuple[bool, str | None, str]:
    """Проверяет, разрешена ли автономная доставка сейчас.

    Возвращает (разрешено, причина_запрета_или_None, режим).
    Режим: execute / verify / escalate / stop.
    """
    budget = await get_or_create_budget(session, user)

    if budget.global_paused:
        return False, "global_paused", "stop"

    now = datetime.now(UTC).replace(tzinfo=None)
    if not (budget.active_start_hour <= now.hour < budget.active_end_hour):
        return False, "outside_active_hours", "stop"

    if (
        budget.allowed_conversation_ids
        and str(conversation.id) not in budget.allowed_conversation_ids
    ):
        return False, "conversation_not_allowed", "escalate"

    if budget.consecutive_errors >= budget.auto_stop_after_errors:
        return False, "auto_stopped_errors", "stop"

    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    sent_today = await session.scalar(
        select(func.count(AgentAction.id)).where(
            AgentAction.user_id == user.id,
            AgentAction.created_at >= today_start,
            AgentAction.status.in_(["sent", "scheduled"]),
        )
    )
    if sent_today is not None and sent_today >= budget.max_messages_per_day:
        return False, "daily_limit_exceeded", "stop"

    return True, None, "execute"


async def record_success(session: AsyncSession, user: User) -> None:
    budget = await get_or_create_budget(session, user)
    budget.consecutive_errors = 0
    budget.last_error_at = None
    await session.flush()


async def record_error(
    session: AsyncSession,
    user: User,
    *,
    conversation_id,
    action_id=None,
    error_type: str,
) -> None:
    _validate_error_type(error_type)
    budget = await get_or_create_budget(session, user)
    budget.consecutive_errors = (budget.consecutive_errors or 0) + 1
    budget.last_error_at = datetime.now(UTC)
    session.add(
        AutonomyErrorLog(
            user_id=user.id,
            conversation_id=conversation_id,
            action_id=action_id,
            error_type=error_type,
        )
    )
    await session.flush()


async def reset_errors(session: AsyncSession, user: User) -> None:
    budget = await get_or_create_budget(session, user)
    budget.consecutive_errors = 0
    budget.last_error_at = None
    await session.flush()


async def list_errors(
    session: AsyncSession,
    *,
    user_id,
    limit: int = 50,
    offset: int = 0,
) -> Sequence[AutonomyErrorLog]:
    result = await session.scalars(
        select(AutonomyErrorLog)
        .where(AutonomyErrorLog.user_id == user_id)
        .order_by(AutonomyErrorLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result)


# --- Калибровка обратной связи ---


def classify_feedback(feedback: UserFeedback) -> str:
    """Классифицирует обратную связь пользователя.

    Правило: явная правка текста (correction) без высокой оценки — фактическая
    ошибка или неверный тон; низкая оценка без правки — неверная стратегия;
    высокая оценка без правки — личное предпочтение.
    """
    correction = bool(feedback.correction and feedback.correction.strip())
    rating = feedback.rating
    if correction and (rating is None or rating <= 3):
        return CLASS_FACTUAL_ERROR
    if correction and rating and rating >= 4:
        return CLASS_WRONG_TONE
    if rating is not None and rating <= 2 and not correction:
        return CLASS_WRONG_STRATEGY
    return CLASS_PERSONAL_PREFERENCE


async def get_or_create_calibration_rule(
    session: AsyncSession,
    user: User,
    rule_type: str,
    condition: dict,
    action: dict,
    confidence: float,
) -> CalibrationRule:
    _validate_rule_type(rule_type)
    confidence = max(CALIBRATION_CONFIDENCE_MIN, min(CALIBRATION_CONFIDENCE_MAX, confidence))
    rule = await session.scalar(
        select(CalibrationRule).where(
            CalibrationRule.user_id == user.id,
            CalibrationRule.rule_type == rule_type,
        )
    )
    if rule is None:
        rule = CalibrationRule(
            user_id=user.id,
            rule_type=rule_type,
            condition=dict(condition),
            action=dict(action),
            confidence=confidence,
        )
        session.add(rule)
        await session.flush()
        await session.refresh(rule)
        return rule
    # Обновляем существующее правило: смешанная уверенность, счётчик применений.
    rule.applies_count = (rule.applies_count or 0) + 1
    rule.last_applied_at = datetime.now(UTC)
    rule.confidence = round((rule.confidence + confidence) / 2, 2)
    rule.condition = dict(condition)
    rule.action = dict(action)
    await session.flush()
    await session.refresh(rule)
    return rule


async def list_calibration_rules(
    session: AsyncSession,
    *,
    user_id,
    rule_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> Sequence[CalibrationRule]:
    query = select(CalibrationRule).where(CalibrationRule.user_id == user_id)
    if rule_type is not None:
        _validate_rule_type(rule_type)
        query = query.where(CalibrationRule.rule_type == rule_type)
    result = await session.scalars(
        query.order_by(CalibrationRule.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result)


async def classify_and_calibrate(
    session: AsyncSession,
    user: User,
    feedback: UserFeedback,
) -> tuple[str, CalibrationRule | None]:
    """Классифицирует отзыв и при закономерности создаёт правило калибровки."""
    classification = classify_feedback(feedback)

    # Закономерность: повторяется ли аналогичная классификация.
    similar_count = await session.scalar(
        select(func.count(UserFeedback.id)).where(
            UserFeedback.user_id == user.id,
            UserFeedback.feedback_type == feedback.feedback_type,
            UserFeedback.id != feedback.id,
        )
    )
    pattern_detected = (similar_count or 0) >= PATTERN_MIN_REPETITIONS - 1

    rule = None
    if pattern_detected and classification in {
        CLASS_WRONG_TONE,
        CLASS_WRONG_STRATEGY,
        CLASS_FACTUAL_ERROR,
    }:
        condition = {
            "feedback_type": feedback.feedback_type,
            "conversation_id": str(feedback.conversation_id) if feedback.conversation_id else None,
        }
        action = {
            "adjustment": classification,
            "confidence": feedback.rating or 3,
        }
        rule = await get_or_create_calibration_rule(
            session,
            user,
            rule_type=RULE_STRATEGY_RULE,
            condition=condition,
            action=action,
            confidence=0.6,
        )

    return classification, rule
