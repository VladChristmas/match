"""Contract-тесты (P3): типы и форма ответов ключевых эндпоинтов API.

Проверяют контракт (schema-уровень), а не бизнес-логику: коды статусов,
уникальность id, типы и обязательность полей, формат timestamp, вид ошибок.
"""

import uuid
from datetime import datetime

TOKEN_HEADER = {"X-Match-Token": "contract-user"}


def _is_uuid(value: object) -> bool:
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def _is_iso8601(value: object) -> bool:
    try:
        datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return True
    except (ValueError, TypeError):
        return False


async def test_root_contract(client):
    response = await client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["service"], str)
    assert isinstance(body["environment"], str)


async def test_health_contract(client):
    for path in ("/health", "/health/ready"):
        response = await client.get(path)
        assert response.status_code == 200, path
        assert isinstance(response.json(), dict), path


async def test_conversation_crud_contract(client):
    created = await client.post(
        "/api/v1/conversations", headers=TOKEN_HEADER, json={"autonomy_mode": "manual"}
    )
    assert created.status_code == 201
    conversation = created.json()
    assert _is_uuid(conversation["id"])
    assert isinstance(conversation["autonomy_mode"], str)
    assert _is_iso8601(conversation["created_at"])

    fetched = await client.get(
        f"/api/v1/conversations/{conversation['id']}", headers=TOKEN_HEADER
    )
    assert fetched.status_code == 200
    assert fetched.json()["id"] == conversation["id"]

    listed = await client.get("/api/v1/conversations", headers=TOKEN_HEADER)
    assert listed.status_code == 200
    assert isinstance(listed.json(), list)
    assert any(item["id"] == conversation["id"] for item in listed.json())


async def test_message_import_and_drafts_contract(client):
    conversation_id = (
        await client.post("/api/v1/conversations", headers=TOKEN_HEADER, json={})
    ).json()["id"]

    imported = await client.post(
        f"/api/v1/conversations/{conversation_id}/messages/import",
        headers=TOKEN_HEADER,
        json={"content": "Привет!", "direction": "inbound"},
    )
    assert imported.status_code == 201
    message = imported.json()
    assert _is_uuid(message["id"])
    assert message["direction"] == "inbound"
    assert _is_iso8601(message["created_at"])

    messages = await client.get(
        f"/api/v1/conversations/{conversation_id}/messages", headers=TOKEN_HEADER
    )
    assert messages.status_code == 200
    assert isinstance(messages.json(), list)

    draft = await client.post(
        f"/api/v1/conversations/{conversation_id}/drafts", headers=TOKEN_HEADER
    )
    assert draft.status_code == 200
    body = draft.json()
    assert isinstance(body["text"], str)
    assert isinstance(body["validation_ok"], bool)
    assert isinstance(body["provider"], str)
    assert isinstance(body["model"], str)
    assert isinstance(body["latency_ms"], int)
    assert isinstance(body["issues"], list)


async def test_profile_contract(client):
    response = await client.get("/api/v1/profile", headers=TOKEN_HEADER)
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body.get("relationship_goals"), list)
    assert isinstance(body.get("values"), list)

    patched = await client.patch(
        "/api/v1/profile",
        headers=TOKEN_HEADER,
        json={"relationship_goals": ["семья"], "values": ["честность"]},
    )
    assert patched.status_code == 200
    after = patched.json()
    assert after["relationship_goals"] == ["семья"]
    assert after["values"] == ["честность"]


async def test_integrations_and_agent_settings_contract(client):
    integrations = await client.get("/api/v1/integrations", headers=TOKEN_HEADER)
    assert integrations.status_code == 200
    assert isinstance(integrations.json(), list)

    settings = await client.get("/api/v1/agent/settings", headers=TOKEN_HEADER)
    assert settings.status_code == 200
    assert isinstance(settings.json(), dict)


async def test_not_found_error_contract(client):
    missing = str(uuid.uuid4())
    response = await client.get(
        f"/api/v1/conversations/{missing}", headers=TOKEN_HEADER
    )
    assert response.status_code == 404
    body = response.json()
    assert "detail" in body
    assert isinstance(body["detail"], str)


async def test_openapi_contract(client):
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    assert spec["info"]["title"] == "Match API"
    assert isinstance(spec["info"]["version"], str)
    assert "/api/v1/conversations" in spec["paths"]
    assert "/health" in spec["paths"]
