"""Vision-слой: приём кадров наблюдения (Этап 10).

Кадр (PNG) приходит с клиента, где он снят через `Windows.Graphics.Capture` (ADR-0008).
Сервер **не сохраняет изображение** (приватность, ADR-0007): он вычисляет отпечаток,
размеры и метаданные и создаёт запись наблюдения. Анализ кадра мультимодальной моделью
ждёт закрытия OQ-8, поэтому `analysis_pending=True`, а `summary` пока пуст.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
from dataclasses import dataclass
from datetime import datetime

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
