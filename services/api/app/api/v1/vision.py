import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import select

from app.api.deps import CurrentUser, RateLimitDep, SessionDep
from app.models import Conversation, VisionObservation
from app.schemas import VisionObservationCreate, VisionObservationRead
from app.vision.service import FrameError, decode_png_frame, record_observation

router = APIRouter(prefix="/api/v1/vision", tags=["vision"])


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


@router.get("/observations", response_model=list[VisionObservationRead])
async def list_observations(
    session: SessionDep,
    user: CurrentUser,
    conversation_id: Annotated[uuid.UUID | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[VisionObservation]:
    query = select(VisionObservation).where(VisionObservation.user_id == user.id)
    if conversation_id is not None:
        query = query.where(VisionObservation.conversation_id == conversation_id)
    result = await session.scalars(
        query.order_by(VisionObservation.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result)


@router.post("/observations", response_model=VisionObservationRead)
async def create_observation(
    payload: VisionObservationCreate,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    rate_limit: RateLimitDep,
) -> VisionObservation:
    conversation = await _user_conversation(session, user, payload.conversation_id)
    try:
        info = decode_png_frame(payload.frame_base64)
    except FrameError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from None

    observation = record_observation(
        session,
        user,
        conversation,
        source_label=payload.source_label,
        info=info,
        captured_at=payload.captured_at,
    )
    await session.commit()
    await session.refresh(observation)
    response.status_code = status.HTTP_201_CREATED
    return observation
