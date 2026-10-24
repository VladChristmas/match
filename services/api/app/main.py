import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.admin import router as admin_router
from app.api.v1.agent import router as agent_router
from app.api.v1.analysis import router as analysis_router
from app.api.v1.autonomy import router as autonomy_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.decisions import router as decisions_router
from app.api.v1.dynamics import router as dynamics_router
from app.api.v1.feedback import router as feedback_router
from app.api.v1.health import router as health_router
from app.api.v1.integrations import router as integrations_router
from app.api.v1.privacy import router as privacy_router
from app.api.v1.profile import router as profile_router
from app.api.v1.tokens import router as tokens_router
from app.api.v1.vision import router as vision_router
from app.config import get_settings

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper())
    if hasattr(logging, settings.log_level.upper())
    else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("match.api")

app = FastAPI(
    title="Match API",
    version="0.1.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

origins = settings.cors_allow_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    rid = request.headers.get("x-request-id") or str(uuid.uuid4())
    try:
        response = await call_next(request)
    except Exception:
        # ServerErrorMiddleware находился бы снаружи и не прошёл через этот слой,
        # поэтому 500 оформляем здесь — иначе ответ об ошибке терял x-request-id.
        logger.exception("unhandled error on %s %s rid=%s", request.method, request.url.path, rid)
        response = JSONResponse(status_code=500, content={"detail": "Internal server error"})
    else:
        logger.info(
            "%s %s -> %s rid=%s",
            request.method,
            request.url.path,
            response.status_code,
            rid,
        )
    response.headers["x-request-id"] = rid
    return response


app.include_router(health_router)
app.include_router(profile_router)
app.include_router(feedback_router)
app.include_router(conversations_router)
app.include_router(analysis_router)
app.include_router(integrations_router)
app.include_router(agent_router)
app.include_router(autonomy_router)
app.include_router(decisions_router)
app.include_router(dynamics_router)
app.include_router(privacy_router)
app.include_router(vision_router)
app.include_router(tokens_router)
app.include_router(admin_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "match-api", "environment": settings.environment}
