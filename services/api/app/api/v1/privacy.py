from datetime import UTC, datetime

from fastapi import APIRouter, Response, status
from sqlalchemy import delete, select

from app.api.deps import CurrentUser, SessionDep
from app.models import (
    AccessToken,
    AgentAction,
    AgentSettings,
    CommunicationProfile,
    CompatibilityAssessment,
    Conversation,
    Message,
    ModelRun,
    RiskAssessment,
    User,
    UserFeedback,
    UserProfile,
    VisionObservation,
)

router = APIRouter(prefix="/api/v1/privacy", tags=["privacy"])


def _dump(obj) -> dict:
    if obj is None:
        return {}
    return {column.name: getattr(obj, column.name) for column in obj.__table__.columns}


@router.get("/export")
async def export_data(session: SessionDep, user: CurrentUser) -> dict:
    """Полный экспорт данных пользователя (персональные данные не собираются сверх созданного)."""
    profile = await session.scalar(
        select(UserProfile).where(UserProfile.user_id == user.id)
    )
    communication = await session.scalar(
        select(CommunicationProfile).where(CommunicationProfile.user_id == user.id)
    )
    agent_settings = await session.scalar(
        select(AgentSettings).where(AgentSettings.user_id == user.id)
    )

    conversations = list(
        await session.scalars(
            select(Conversation)
            .where(Conversation.user_id == user.id)
            .order_by(Conversation.created_at.asc())
        )
    )
    conversations_out = []
    for conversation in conversations:
        messages = list(
            await session.scalars(
                select(Message)
                .where(Message.conversation_id == conversation.id)
                .order_by(Message.created_at.asc())
            )
        )
        conversations_out.append({**_dump(conversation), "messages": [_dump(m) for m in messages]})

    async def many(model) -> list[dict]:
        rows = await session.scalars(select(model).where(model.user_id == user.id))
        return [_dump(row) for row in rows]

    return {
        "exported_at": datetime.now(UTC),
        "user": {**_dump(user), "token_ref": "redacted"},
        "profile": _dump(profile),
        "communication": _dump(communication),
        "feedback": await many(UserFeedback),
        "conversations": conversations_out,
        "compatibility": await many(CompatibilityAssessment),
        "risk": await many(RiskAssessment),
        "agent_settings": _dump(agent_settings),
        "agent_actions": await many(AgentAction),
        "model_runs": await many(ModelRun),
        "vision_observations": await many(VisionObservation),
        "access_tokens": [
            {
                "id": record.id,
                "label": record.label,
                "created_at": record.created_at,
                "last_used_at": record.last_used_at,
                "revoked_at": record.revoked_at,
            }
            for record in await session.scalars(
                select(AccessToken).where(AccessToken.user_id == user.id)
            )
        ],
    }


@router.post("/deletion-request", status_code=status.HTTP_204_NO_CONTENT)
async def deletion_request(session: SessionDep, user: CurrentUser) -> Response:
    """Удаление всех данных пользователя. Порядок удаления не зависит от FK-каскада СУБД."""
    conversation_ids = list(
        await session.scalars(select(Conversation.id).where(Conversation.user_id == user.id))
    )
    if conversation_ids:
        await session.execute(delete(Message).where(Message.conversation_id.in_(conversation_ids)))
    for model in (
        AgentAction,
        UserFeedback,
        CompatibilityAssessment,
        RiskAssessment,
        ModelRun,
        VisionObservation,
        Conversation,
    ):
        await session.execute(delete(model).where(model.user_id == user.id))
    for model in (UserProfile, CommunicationProfile, AgentSettings):
        await session.execute(delete(model).where(model.user_id == user.id))
    await session.execute(delete(AccessToken).where(AccessToken.user_id == user.id))
    await session.execute(delete(User).where(User.id == user.id))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
