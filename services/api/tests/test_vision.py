import base64
import struct
import zlib

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import get_settings
from app.main import app
from app.models import ModelRun
from app.vision.base import VisionRequest, VisionResponse
from app.vision.gateway import VisionGateway, get_vision_gateway

TOKEN_HEADER = {"X-Match-Token": "vision-user"}


class FakeVisionProvider:
    def __init__(self, text="В окне видно переписку.", error=None) -> None:
        self.name = "fake"
        self.model = "fake-1"
        self._text = text
        self._error = error

    async def analyze(self, request: VisionRequest) -> VisionResponse:
        if self._error is not None:
            raise RuntimeError(self._error)
        return VisionResponse(
            text=self._text,
            provider=self.name,
            model=self.model,
            latency_ms=5,
            token_usage=42,
        )


@pytest.fixture(autouse=True)
def no_vision_network():
    app.dependency_overrides[get_vision_gateway] = lambda: VisionGateway([])
    yield
    app.dependency_overrides.pop(get_vision_gateway, None)


def png_bytes(width: int = 2, height: int = 2) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        payload = kind + data
        crc = zlib.crc32(payload) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + payload + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = b"\x00" + b"\xff\x00\x00" * width
    raw = row * height
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def frame_b64(width: int = 2, height: int = 2) -> str:
    return base64.b64encode(png_bytes(width, height)).decode("ascii")


async def _conversation(client, headers=TOKEN_HEADER) -> str:
    created = await client.post("/api/v1/conversations", headers=headers, json={})
    assert created.status_code == 201
    return created.json()["id"]


async def test_observations_require_token(client):
    assert (await client.get("/api/v1/vision/observations")).status_code == 401


async def test_create_observation_stores_metadata_only(client):
    conversation_id = await _conversation(client)
    response = await client.post(
        "/api/v1/vision/observations",
        headers=TOKEN_HEADER,
        json={
            "conversation_id": conversation_id,
            "frame_base64": frame_b64(width=3, height=5),
            "source_label": "MATCH window",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["frame_width"] == 3
    assert body["frame_height"] == 5
    assert body["frame_bytes"] > 0
    assert len(body["content_sha256"]) == 64
    assert body["analysis_pending"] is True
    assert body["summary"] is None
    assert "frame_base64" not in body

    listed = await client.get(
        f"/api/v1/vision/observations?conversation_id={conversation_id}",
        headers=TOKEN_HEADER,
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1


async def test_rejects_non_png_frame(client):
    conversation_id = await _conversation(client)
    response = await client.post(
        "/api/v1/vision/observations",
        headers=TOKEN_HEADER,
        json={
            "conversation_id": conversation_id,
            "frame_base64": base64.b64encode(b"not a png").decode("ascii"),
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "frame must be a PNG image"


async def test_rejects_invalid_base64(client):
    conversation_id = await _conversation(client)
    response = await client.post(
        "/api/v1/vision/observations",
        headers=TOKEN_HEADER,
        json={"conversation_id": conversation_id, "frame_base64": "!!!not-base64!!!"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "frame is not valid base64"


async def test_rejects_foreign_conversation(client):
    conversation_id = await _conversation(client, headers={"X-Match-Token": "someone-else"})
    response = await client.post(
        "/api/v1/vision/observations",
        headers=TOKEN_HEADER,
        json={"conversation_id": conversation_id, "frame_base64": frame_b64()},
    )
    assert response.status_code == 404


async def test_observations_are_isolated_per_user(client):
    conversation_id = await _conversation(client)
    await client.post(
        "/api/v1/vision/observations",
        headers=TOKEN_HEADER,
        json={"conversation_id": conversation_id, "frame_base64": frame_b64()},
    )
    other = await client.get(
        "/api/v1/vision/observations", headers={"X-Match-Token": "other-vision-user"}
    )
    assert other.status_code == 200
    assert other.json() == []


def _use_gateway(*providers) -> None:
    app.dependency_overrides[get_vision_gateway] = lambda: VisionGateway(list(providers))


async def test_analysis_populates_summary(client, engine):
    _use_gateway(FakeVisionProvider())
    conversation_id = await _conversation(client)
    response = await client.post(
        "/api/v1/vision/observations",
        headers=TOKEN_HEADER,
        json={"conversation_id": conversation_id, "frame_base64": frame_b64()},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["analysis_pending"] is False
    assert body["summary"] == "В окне видно переписку."
    assert body["provider"] == "fake"
    assert body["model"] == "fake-1"

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        runs = list(await session.scalars(select(ModelRun)))
    assert len(runs) == 1
    assert runs[0].task_type == "vision_observation"
    assert runs[0].provider == "fake"


async def test_analysis_can_be_skipped(client):
    _use_gateway(FakeVisionProvider())
    conversation_id = await _conversation(client)
    response = await client.post(
        "/api/v1/vision/observations",
        headers=TOKEN_HEADER,
        json={
            "conversation_id": conversation_id,
            "frame_base64": frame_b64(),
            "analyze": False,
        },
    )
    assert response.status_code == 201
    assert response.json()["analysis_pending"] is True
    assert response.json()["summary"] is None


async def test_failed_analysis_keeps_observation_pending(client):
    _use_gateway(FakeVisionProvider(error="model offline"))
    conversation_id = await _conversation(client)
    response = await client.post(
        "/api/v1/vision/observations",
        headers=TOKEN_HEADER,
        json={"conversation_id": conversation_id, "frame_base64": frame_b64()},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["analysis_pending"] is True
    assert body["summary"] is None
    assert body["provider"] is None
    assert len(body["content_sha256"]) == 64


async def test_analysis_throttled_by_min_interval(client, monkeypatch):
    _use_gateway(FakeVisionProvider())
    conversation_id = await _conversation(client)
    payload = {"conversation_id": conversation_id, "frame_base64": frame_b64()}

    monkeypatch.setenv("MATCH_VISION_MIN_INTERVAL_SECONDS", "60")
    get_settings.cache_clear()
    try:
        first = await client.post("/api/v1/vision/observations", headers=TOKEN_HEADER, json=payload)
        second = await client.post(
            "/api/v1/vision/observations", headers=TOKEN_HEADER, json=payload
        )
    finally:
        get_settings.cache_clear()

    assert first.status_code == 201
    assert first.json()["analysis_pending"] is False
    assert first.json()["summary"] == "В окне видно переписку."
    assert second.status_code == 201
    assert second.json()["analysis_pending"] is True
    assert second.json()["summary"] is None
    assert len(second.json()["content_sha256"]) == 64


async def test_analysis_respects_user_limit(client, monkeypatch):
    _use_gateway(FakeVisionProvider())
    conversation_id = await _conversation(client)
    payload = {"conversation_id": conversation_id, "frame_base64": frame_b64()}

    monkeypatch.setenv("MATCH_LLM_USER_REQUEST_LIMIT", "1")
    get_settings.cache_clear()
    try:
        first = await client.post("/api/v1/vision/observations", headers=TOKEN_HEADER, json=payload)
        second = await client.post(
            "/api/v1/vision/observations", headers=TOKEN_HEADER, json=payload
        )
    finally:
        get_settings.cache_clear()

    assert first.status_code == 201
    assert first.json()["analysis_pending"] is False
    assert second.status_code == 429
