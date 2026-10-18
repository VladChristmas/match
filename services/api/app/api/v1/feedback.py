from fastapi import APIRouter, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.models import UserFeedback
from app.schemas import FeedbackCreate, FeedbackRead

router = APIRouter(prefix="/api/v1/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackRead, status_code=status.HTTP_201_CREATED)
async def create_feedback(
    payload: FeedbackCreate, session: SessionDep, user: CurrentUser
) -> UserFeedback:
    feedback = UserFeedback(user_id=user.id, **payload.model_dump())
    session.add(feedback)
    await session.commit()
    await session.refresh(feedback)
    return feedback


@router.get("", response_model=list[FeedbackRead])
async def list_feedback(
    session: SessionDep,
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[UserFeedback]:
    result = await session.scalars(
        select(UserFeedback)
        .where(UserFeedback.user_id == user.id)
        .order_by(UserFeedback.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result)
