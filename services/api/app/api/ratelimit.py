"""Ограничение нагрузки: запросы на пользователя в минуту.

Два бэкенда (Этап 14), переключаются `MATCH_RATE_LIMIT_BACKEND`:

- `memory` — in-process скользящее окно, потокобезопасно, но считает только один инстанс;
- `db` — счётчики в таблице `rate_limit_counters` (фиксированные окна по 60 с), работают
  при нескольких инстансах без внешней инфраструктуры (Redis не требуется).

Лимит `MATCH_RATE_LIMIT_PER_MINUTE = 0` отключает проверку (в обоих режимах).
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from datetime import UTC, datetime
from threading import Lock

from fastapi import HTTPException, status
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import RateLimitCounter

_WINDOW_SECONDS = 60.0
_lock = Lock()
_hits: dict[str, deque[float]] = defaultdict(deque)


def reset_rate_limit() -> None:
    with _lock:
        _hits.clear()


def _memory_hits(key: str) -> int:
    """Число запросов в скользящем окне (без регистрации текущего)."""
    now = time.monotonic()
    with _lock:
        bucket = _hits[key]
        while bucket and now - bucket[0] > _WINDOW_SECONDS:
            bucket.popleft()
        return len(bucket)


def _memory_add(key: str) -> None:
    with _lock:
        _hits[key].append(time.monotonic())


def _window_start(now: datetime) -> datetime:
    return now.replace(second=0, microsecond=0)


async def _db_hits(session: AsyncSession, key: str, window_start: datetime) -> int:
    """Число запросов в текущем окне; устаревшие окна пользователя удаляются."""
    await session.execute(
        delete(RateLimitCounter).where(
            RateLimitCounter.key == key,
            RateLimitCounter.window_start < window_start,
        )
    )
    current = await session.scalar(
        select(RateLimitCounter.count).where(
            RateLimitCounter.key == key,
            RateLimitCounter.window_start == window_start,
        )
    )
    return current or 0


async def _db_increment(session: AsyncSession, key: str, window_start: datetime) -> None:
    """Регистрирует запрос в текущем окне (upsert, устойчив к гонкам)."""
    current = await _db_hits(session, key, window_start)
    if current == 0:
        try:
            async with session.begin_nested():
                session.add(RateLimitCounter(key=key, window_start=window_start, count=1))
        except IntegrityError:
            await session.execute(
                update(RateLimitCounter)
                .where(
                    RateLimitCounter.key == key,
                    RateLimitCounter.window_start == window_start,
                )
                .values(count=RateLimitCounter.count + 1)
            )
    else:
        await session.execute(
            update(RateLimitCounter)
            .where(
                RateLimitCounter.key == key,
                RateLimitCounter.window_start == window_start,
            )
            .values(count=current + 1)
        )
    await session.commit()


def _too_many() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Rate limit exceeded",
    )


async def enforce_rate_limit(session: AsyncSession | None, key: str) -> None:
    limit = get_settings().rate_limit_per_minute
    if limit <= 0:
        return

    if get_settings().rate_limit_backend == "db":
        if session is None:
            raise RuntimeError("DB rate limit backend requires a session")
        window_start = _window_start(datetime.now(UTC))
        if await _db_hits(session, key, window_start) >= limit:
            raise _too_many()
        await _db_increment(session, key, window_start)
        return

    if _memory_hits(key) >= limit:
        raise _too_many()
    _memory_add(key)


def user_key(user_id: uuid.UUID) -> str:
    return str(user_id)
