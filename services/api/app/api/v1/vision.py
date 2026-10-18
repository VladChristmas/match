import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import select

from app.api.deps import CurrentUser, RateLimitDep, SessionDep, VisionGatewayDep
from app.config import get_settings
from app.llm.limits import count_user_runs, is_limit_reached
from app.models import Conversation, ModelRun, VisionObservation
from app.schemas import VisionObservationCreate, VisionObservationRead
from app.vision.base import VisionRequest
from app.vision.gateway import VisionUnavailable
from app.vision.service import (
    FrameError,
    decode_png_frame,
    is_analysis_throttled,
    record_observation,
)

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
    gateway: VisionGatewayDep,
    rate_limit: RateLimitDep,
) -> VisionObservation:
    conversation = await _user_conversation(session, user, payload.conversation_id)
    try:
        info = decode_png_frame(payload.frame_base64)
    except FrameError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from None

    settings = get_settings()
    observation = record_observation(
        session,
        user,
        conversation,
        source_label=payload.source_label,
        info=info,
        captured_at=payload.captured_at,
    )

    throttled = await is_analysis_throttled(session, user.id, settings.vision_min_interval_seconds)
    if payload.analyze and gateway.available and not throttled:
        used = await count_user_runs(session, user.id)
        if is_limit_reached(used, settings.llm_user_request_limit):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="LLM request limit reached",
            )
        request = VisionRequest(
            image_base64=payload.frame_base64,
            instruction=settings.vision_prompt,
            max_tokens=settings.vision_max_tokens,
            temperature=settings.vision_temperature,
        )
        try:
            outcome = await gateway.analyze(request)
        except VisionUnavailable:
            outcome = None
        if outcome is not None:
            observation.summary = outcome.text
            observation.analysis_pending = False
            observation.provider = outcome.provider
            observation.model = outcome.model
            session.add(
                ModelRun(
                    user_id=user.id,
                    task_type="vision_observation",
                    provider=outcome.provider,
                    model=outcome.model,
                    model_version=outcome.model,
                    prompt_version="vision-observation-v1",
                    latency_ms=outcome.latency_ms,
                    token_usage=outcome.token_usage,
                    status="ok",
                )
            )

    await session.commit()
    await session.refresh(observation)
    response.status_code = status.HTTP_201_CREATED
    return observation
