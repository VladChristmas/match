"""Простое ограничение нагрузки: скользящее окно запросов на пользователя.

In-process и потокобезопасно; предназначено для одного инстанса. Для горизонтального
масштабирования заменяется на внешний лимитер (Redis) — отметить в OQ/ADR.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, status

from app.config import get_settings

_WINDOW_SECONDS = 60.0
_lock = Lock()
_hits: dict[str, deque[float]] = defaultdict(deque)


def reset_rate_limit() -> None:
    with _lock:
        _hits.clear()


def enforce_rate_limit(key: str) -> None:
    limit = get_settings().rate_limit_per_minute
    if limit <= 0:
        return
    now = time.monotonic()
    with _lock:
        bucket = _hits[key]
        while bucket and now - bucket[0] > _WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
            )
        bucket.append(now)
