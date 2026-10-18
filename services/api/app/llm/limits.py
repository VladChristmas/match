import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ModelRun


async def count_user_runs(session: AsyncSession, user_id: uuid.UUID) -> int:
    total = await session.scalar(
        select(func.count()).select_from(ModelRun).where(ModelRun.user_id == user_id)
    )
    return total or 0


def is_limit_reached(used: int, limit: int) -> bool:
    return limit > 0 and used >= limit
