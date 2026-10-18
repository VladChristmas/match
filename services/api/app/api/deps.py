from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.service import maybe_promote_admin
from app.api.ratelimit import enforce_rate_limit, user_key
from app.auth.service import is_known_token, resolve_access_token
from app.config import get_settings
from app.db import get_session
from app.integrations.registry import IntegrationRegistry, get_registry
from app.llm.gateway import LLMGateway, get_gateway
from app.models import User
from app.vision.gateway import VisionGateway, get_vision_gateway

SessionDep = Annotated[AsyncSession, Depends(get_session)]
GatewayDep = Annotated[LLMGateway, Depends(get_gateway)]
RegistryDep = Annotated[IntegrationRegistry, Depends(get_registry)]
VisionGatewayDep = Annotated[VisionGateway, Depends(get_vision_gateway)]


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


async def get_current_user(
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
    x_match_token: Annotated[str | None, Header()] = None,
) -> User:
    token = _extract_bearer_token(authorization) or x_match_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing access token",
        )

    user = await resolve_access_token(session, token)
    if user is None:
        if not get_settings().auth_allow_legacy_tokens or await is_known_token(session, token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token",
            )

        user = await session.scalar(select(User).where(User.token_ref == token))
        if user is None:
            user = User(token_ref=token)
            session.add(user)
            await session.commit()
            await session.refresh(user)

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not active",
        )
    return await maybe_promote_admin(session, user)


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_admin_user(user: CurrentUser) -> User:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


AdminUser = Annotated[User, Depends(get_admin_user)]


async def rate_limit_dependency(user: CurrentUser, session: SessionDep) -> None:
    await enforce_rate_limit(session, user_key(user.id))


RateLimitDep = Annotated[None, Depends(rate_limit_dependency)]
