from fastapi import APIRouter

from app.admin.service import collect_metrics
from app.api.deps import AdminUser, SessionDep
from app.schemas import AdminMetrics

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/metrics", response_model=AdminMetrics)
async def metrics(session: SessionDep, admin: AdminUser) -> dict:
    return await collect_metrics(session)


@router.get("/whoami")
async def whoami(admin: AdminUser) -> dict[str, str]:
    return {"user_id": str(admin.id), "role": admin.role}
