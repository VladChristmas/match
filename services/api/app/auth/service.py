"""Токены доступа (Этап 12, OQ-7).

Пользовательский токен генерируется сервером (`secrets.token_urlsafe`), наружу отдаётся
один раз при выдаче; в БД хранится только SHA-256 хэш. Токен можно отозвать и ротировать.
Легаси-схема `token_ref` (ADR-0010) остаётся для разработки и включается настройкой
`MATCH_AUTH_ALLOW_LEGACY_TOKENS`.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AccessToken, User

TOKEN_PREFIX = "match_"
LAST_USED_REFRESH_SECONDS = 3600


def generate_token() -> str:
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def resolve_access_token(session: AsyncSession, token: str) -> User | None:
    """Возвращает активного пользователя по токену. Обновляет `last_used_at`."""
    record = await session.scalar(
        select(AccessToken).where(AccessToken.token_hash == hash_token(token))
    )
    if record is None or record.revoked_at is not None:
        return None
    user = await session.get(User, record.user_id)
    if user is None:
        return None
    now = datetime.now(UTC)
    last = record.last_used_at
    if last is None or (now - _aware(last)).total_seconds() > LAST_USED_REFRESH_SECONDS:
        record.last_used_at = now
        await session.commit()
    return user


async def is_known_token(session: AsyncSession, token: str) -> bool:
    """Токен уже выдавался (в том числе отозван) — легаси-путь для него запрещён."""
    found = await session.scalar(
        select(AccessToken.id).where(AccessToken.token_hash == hash_token(token))
    )
    return found is not None


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


async def create_token(
    session: AsyncSession, user: User, label: str
) -> tuple[AccessToken, str]:
    token = generate_token()
    record = AccessToken(user_id=user.id, token_hash=hash_token(token), label=label)
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record, token


async def list_tokens(session: AsyncSession, user: User) -> list[AccessToken]:
    result = await session.scalars(
        select(AccessToken)
        .where(AccessToken.user_id == user.id)
        .order_by(AccessToken.created_at.desc())
    )
    return list(result)


async def get_owned_token(
    session: AsyncSession, user: User, token_id: uuid.UUID
) -> AccessToken | None:
    return await session.scalar(
        select(AccessToken).where(
            AccessToken.id == token_id,
            AccessToken.user_id == user.id,
        )
    )


async def revoke_token(session: AsyncSession, record: AccessToken) -> AccessToken:
    if record.revoked_at is None:
        record.revoked_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(record)
    return record


async def rotate_token(
    session: AsyncSession, user: User, record: AccessToken
) -> tuple[AccessToken, str]:
    await revoke_token(session, record)
    label = record.label or "rotated"
    return await create_token(session, user, label)
