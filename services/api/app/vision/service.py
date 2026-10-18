"""Vision-слой: приём кадров наблюдения (Этап 10) и троттлинг анализа (Этап 17).

Кадр (PNG) приходит с клиента, где он снят через `Windows.Graphics.Capture` (ADR-0008).
Сервер **не сохраняет изображение** (приватность, ADR-0007): он вычисляет отпечаток,
размеры и метаданные и создаёт запись наблюдения. Анализ кадра мультимодальной моделью
выполняет `app/vision/gateway.py` (ADR-0018); частоту вызовов модели ограничивает
`MATCH_VISION_MIN_INTERVAL_SECONDS` (ADR-0023).
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, User, VisionObservation

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
MAX_FRAME_BYTES = 8 * 1024 * 1024


class FrameError(ValueError):
    """Кадр отклонён: не PNG, повреждён или слишком большой."""


@dataclass(frozen=True)
class FrameInfo:
    bytes_len: int
    width: int
    height: int
    sha256: str


def decode_png_frame(frame_base64: str) -> FrameInfo:
    try:
        raw = base64.b64decode(frame_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise FrameError("frame is not valid base64") from exc

    if not raw.startswith(PNG_MAGIC) or len(raw) < 24:
        raise FrameError("frame must be a PNG image")
    if len(raw) > MAX_FRAME_BYTES:
        raise FrameError("frame exceeds size limit")

    width = int.from_bytes(raw[16:20], "big")
    height = int.from_bytes(raw[20:24], "big")
    if width <= 0 or height <= 0:
        raise FrameError("frame has invalid dimensions")

    return FrameInfo(
        bytes_len=len(raw),
        width=width,
        height=height,
        sha256=hashlib.sha256(raw).hexdigest(),
    )


def record_observation(
    session: AsyncSession,
    user: User,
    conversation: Conversation,
    *,
    source_label: str,
    info: FrameInfo,
    captured_at: datetime | None,
) -> VisionObservation:
    observation = VisionObservation(
        user_id=user.id,
        conversation_id=conversation.id,
        source_label=source_label,
        frame_width=info.width,
        frame_height=info.height,
        frame_bytes=info.bytes_len,
        content_sha256=info.sha256,
        analysis_pending=True,
        summary=None,
        captured_at=captured_at,
    )
    session.add(observation)
    return observation


async def is_analysis_throttled(
    session: AsyncSession, user_id: uuid.UUID, min_interval_seconds: float
) -> bool:
    """True, если недавно уже анализировался кадр этого пользователя (троттлинг, ADR-0023).

    Кадр всё равно записывается как наблюдение; пропускается только вызов модели.
    `min_interval_seconds <= 0` отключает ограничение.
    """
    if min_interval_seconds <= 0:
        return False
    threshold = datetime.now(UTC) - timedelta(seconds=min_interval_seconds)
    recent = await session.scalar(
        select(VisionObservation.id)
        .where(
            VisionObservation.user_id == user_id,
            VisionObservation.analysis_pending.is_(False),
            VisionObservation.created_at >= threshold,
        )
        .limit(1)
    )
    return recent is not None
