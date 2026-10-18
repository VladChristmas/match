import uuid

from fastapi import APIRouter, HTTPException, Response, status

from app.api.deps import CurrentUser, RateLimitDep, SessionDep
from app.auth.service import (
    create_token,
    get_owned_token,
    list_tokens,
    revoke_token,
    rotate_token,
)
from app.models import AccessToken
from app.schemas import AccessTokenCreate, AccessTokenIssued, AccessTokenRead

router = APIRouter(prefix="/api/v1/tokens", tags=["tokens"])


@router.get("", response_model=list[AccessTokenRead])
async def read_tokens(session: SessionDep, user: CurrentUser) -> list[AccessToken]:
    return await list_tokens(session, user)


@router.post("", response_model=AccessTokenIssued, status_code=status.HTTP_201_CREATED)
async def issue_token(
    payload: AccessTokenCreate,
    session: SessionDep,
    user: CurrentUser,
    rate_limit: RateLimitDep,
) -> AccessTokenIssued:
    record, token = await create_token(session, user, payload.label)
    return AccessTokenIssued(
        id=record.id,
        token=token,
        label=record.label,
        created_at=record.created_at,
    )


@router.post("/{token_id}/rotate", response_model=AccessTokenIssued)
async def rotate(
    token_id: uuid.UUID, session: SessionDep, user: CurrentUser, rate_limit: RateLimitDep
) -> AccessTokenIssued:
    record = await get_owned_token(session, user, token_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found")
    if record.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Token already revoked"
        )
    new_record, token = await rotate_token(session, user, record)
    return AccessTokenIssued(
        id=new_record.id,
        token=token,
        label=new_record.label,
        created_at=new_record.created_at,
    )


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke(
    token_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> Response:
    record = await get_owned_token(session, user, token_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found")
    await revoke_token(session, record)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
