"""Decision Loop API (Этап 23, ADR-0029).

`POST /agent/decisions/evaluate` — вычислить и показать решение без побочных эффектов
(агент объясняет, почему выбрал действие, другой вариант или паузу).
`GET /agent/decisions` — журнал решений пользователя (прозрачность).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.decision import build_state, decide, persist_decision
from app.models import AgentDecision, Conversation
from app.schemas import AgentDecisionRead, DecisionEvaluateRequest

router = APIRouter(prefix="/api/v1/agent", tags=["decisions"])


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


@router.post("/decisions/evaluate", response_model=AgentDecisionRead)
async def evaluate_decision(
    payload: DecisionEvaluateRequest, session: SessionDep, user: CurrentUser
) -> AgentDecision:
    conversation = await _user_conversation(session, user, payload.conversation_id)
    state = await build_state(session, user, conversation, trigger_text=payload.trigger_text)
    decision = decide(state, trigger_text=payload.trigger_text)
    record = persist_decision(
        session,
        user_id=user.id,
        conversation_id=conversation.id,
        decision=decision,
    )
    await session.commit()
    await session.refresh(record)
    return record


@router.get("/decisions", response_model=list[AgentDecisionRead])
async def list_decisions(
    session: SessionDep,
    user: CurrentUser,
    conversation_id: Annotated[uuid.UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AgentDecision]:
    query = select(AgentDecision).where(AgentDecision.user_id == user.id)
    if conversation_id is not None:
        query = query.where(AgentDecision.conversation_id == conversation_id)
    result = await session.scalars(
        query.order_by(AgentDecision.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result)
