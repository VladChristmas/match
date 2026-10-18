"""Сквозной сценарий (Этап 22): токен → профиль → диалог → анализ → автономность →
vision → приватность. Проверяет, что этапы 1–21 работают вместе."""

import base64
import struct
import zlib
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.agent.worker import deliver_due
from app.main import app
from app.vision.gateway import VisionGateway, get_vision_gateway

TOKEN_HEADER = {"X-Match-Token": "e2e-user"}


@pytest.fixture(autouse=True)
def no_vision_network():
    app.dependency_overrides[get_vision_gateway] = lambda: VisionGateway([])
    yield
    app.dependency_overrides.pop(get_vision_gateway, None)


def _png_b64() -> str:
    def chunk(kind: bytes, data: bytes) -> bytes:
        payload = kind + data
        return (
            struct.pack(">I", len(data))
            + payload
            + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0)
    raw = (b"\x00" + b"\xff\x00\x00" * 2) * 2
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw))
    return base64.b64encode(png + chunk(b"IEND", b"")).decode("ascii")


async def test_full_user_flow(client, engine):
    # Профиль и цели/ценности.
    profile = await client.patch(
        "/api/v1/profile",
        headers=TOKEN_HEADER,
        json={"relationship_goals": ["семья"], "values": ["честность"]},
    )
    assert profile.status_code == 200

    # Разговор и входящее сообщение.
    conversation = await client.post(
        "/api/v1/conversations", headers=TOKEN_HEADER, json={"autonomy_mode": "auto_send"}
    )
    conversation_id = conversation.json()["id"]
    imported = await client.post(
        f"/api/v1/conversations/{conversation_id}/messages/import",
        headers=TOKEN_HEADER,
        json={"content": "Привет! Как дела?", "direction": "inbound"},
    )
    assert imported.status_code == 201

    # Черновик (провайдер echo в тестах).
    draft = await client.post(
        f"/api/v1/conversations/{conversation_id}/drafts", headers=TOKEN_HEADER
    )
    assert draft.status_code == 200
    assert draft.json()["text"]

    # Совместимость и риск.
    compatibility = await client.post(
        "/api/v1/analysis/compatibility",
        headers=TOKEN_HEADER,
        json={"counterpart": {"goals": ["семья"], "values": ["честность"]}},
    )
    assert compatibility.status_code == 201
    risk = await client.post(
        "/api/v1/analysis/risk",
        headers=TOKEN_HEADER,
        json={"conversation_id": conversation_id},
    )
    assert risk.status_code == 201

    # Обратная связь.
    feedback = await client.post(
        "/api/v1/feedback",
        headers=TOKEN_HEADER,
        json={"feedback_type": "draft", "rating": 5, "conversation_id": conversation_id},
    )
    assert feedback.status_code in (200, 201)

    # Отложенное действие агента → доставляет внешний воркер.
    scheduled = await client.post(
        "/api/v1/agent/actions",
        headers=TOKEN_HEADER,
        json={
            "conversation_id": conversation_id,
            "text": "Привет! Всё хорошо, а у тебя?",
            "generate": False,
            "schedule_in_seconds": 60,
        },
    )
    assert scheduled.status_code == 201
    assert scheduled.json()["status"] == "scheduled"

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        assert await deliver_due(session, now=datetime.now(UTC) + timedelta(minutes=5)) == 1

    messages = await client.get(
        f"/api/v1/conversations/{conversation_id}/messages", headers=TOKEN_HEADER
    )
    outbound = [item for item in messages.json() if item["direction"] == "outbound"]
    assert len(outbound) == 1
    assert outbound[0]["source"] == "agent"

    # Vision-наблюдение (без сети: провайдеров нет → analysis_pending).
    observation = await client.post(
        "/api/v1/vision/observations",
        headers=TOKEN_HEADER,
        json={
            "conversation_id": conversation_id,
            "frame_base64": _png_b64(),
            "source_label": "MATCH window",
            "analyze": True,
        },
    )
    assert observation.status_code == 201
    assert observation.json()["analysis_pending"] is True

    # Приватность: экспорт и удаление.
    export = await client.get("/api/v1/privacy/export", headers=TOKEN_HEADER)
    assert export.status_code == 200
    body = export.json()
    assert body["user"]["token_ref"] == "redacted"
    assert len(body["conversations"]) == 1
    assert len(body["agent_actions"]) == 1
    assert len(body["vision_observations"]) == 1

    deletion = await client.post("/api/v1/privacy/deletion-request", headers=TOKEN_HEADER)
    assert deletion.status_code == 204

    after = await client.get("/api/v1/privacy/export", headers=TOKEN_HEADER)
    assert after.status_code == 200
    assert after.json()["conversations"] == []
    assert after.json()["vision_observations"] == []
