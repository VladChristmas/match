from fastapi import FastAPI

from app.api.v1.admin import router as admin_router
from app.api.v1.agent import router as agent_router
from app.api.v1.analysis import router as analysis_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.feedback import router as feedback_router
from app.api.v1.health import router as health_router
from app.api.v1.integrations import router as integrations_router
from app.api.v1.privacy import router as privacy_router
from app.api.v1.profile import router as profile_router
from app.api.v1.tokens import router as tokens_router
from app.api.v1.vision import router as vision_router
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Match API",
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.include_router(health_router)
app.include_router(profile_router)
app.include_router(feedback_router)
app.include_router(conversations_router)
app.include_router(analysis_router)
app.include_router(integrations_router)
app.include_router(agent_router)
app.include_router(privacy_router)
app.include_router(vision_router)
app.include_router(tokens_router)
app.include_router(admin_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "match-api", "environment": settings.environment}
