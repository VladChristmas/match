TOKEN_HEADER = {"X-Match-Token": "agent-user"}


async def _create_conversation(client, autonomy_mode="auto_send"):
    response = await client.post(
        "/api/v1/conversations",
        headers=TOKEN_HEADER,
        json={"autonomy_mode": autonomy_mode},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def test_agent_settings_requires_token(client):
    response = await client.get("/api/v1/agent/settings")
    assert response.status_code == 401


async def test_settings_created_with_defaults(client):
    response = await client.get("/api/v1/agent/settings", headers=TOKEN_HEADER)
    assert response.status_code == 200
    body = response.json()
    assert body["default_autonomy_mode"] == "auto_send"
    assert body["queue_paused"] is False


async def test_pause_and_resume(client):
    paused = await client.post("/api/v1/agent/pause", headers=TOKEN_HEADER)
    assert paused.json()["queue_paused"] is True
    resumed = await client.post("/api/v1/agent/resume", headers=TOKEN_HEADER)
    assert resumed.json()["queue_paused"] is False


async def test_auto_send_delivers_immediately(client):
    conversation_id = await _create_conversation(client, "auto_send")
    response = await client.post(
        "/api/v1/agent/actions",
        headers=TOKEN_HEADER,
        json={"conversation_id": conversation_id},
    )
    assert response.status_code == 201
    assert response.json()["status"] == "sent"

    messages = await client.get(
        f"/api/v1/conversations/{conversation_id}/messages", headers=TOKEN_HEADER
    )
    outbound = [m for m in messages.json() if m["direction"] == "outbound"]
    assert len(outbound) == 1
    assert outbound[0]["source"] == "agent"


async def test_paused_queues_for_human(client):
    conversation_id = await _create_conversation(client, "auto_send")
    await client.post("/api/v1/agent/pause", headers=TOKEN_HEADER)

    created = await client.post(
        "/api/v1/agent/actions",
        headers=TOKEN_HEADER,
        json={"conversation_id": conversation_id},
    )
    assert created.status_code == 201
    action = created.json()
    assert action["status"] == "pending"

    approved = await client.post(
        f"/api/v1/agent/actions/{action['id']}/approve", headers=TOKEN_HEADER
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "sent"

    messages = await client.get(
        f"/api/v1/conversations/{conversation_id}/messages", headers=TOKEN_HEADER
    )
    assert any(m["direction"] == "outbound" for m in messages.json())


async def test_reject_pending_action(client):
    conversation_id = await _create_conversation(client, "suggest")
    created = await client.post(
        "/api/v1/agent/actions",
        headers=TOKEN_HEADER,
        json={"conversation_id": conversation_id},
    )
    action = created.json()
    assert action["status"] == "pending"

    rejected = await client.post(
        f"/api/v1/agent/actions/{action['id']}/reject", headers=TOKEN_HEADER
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"

    messages = await client.get(
        f"/api/v1/conversations/{conversation_id}/messages", headers=TOKEN_HEADER
    )
    assert messages.json() == []


async def test_approve_non_pending_conflicts(client):
    conversation_id = await _create_conversation(client, "auto_send")
    created = await client.post(
        "/api/v1/agent/actions",
        headers=TOKEN_HEADER,
        json={"conversation_id": conversation_id},
    )
    action_id = created.json()["id"]
    response = await client.post(
        f"/api/v1/agent/actions/{action_id}/approve", headers=TOKEN_HEADER
    )
    assert response.status_code == 409


async def test_idempotency_key_returns_same_action(client):
    conversation_id = await _create_conversation(client, "auto_send")
    headers = {**TOKEN_HEADER, "Idempotency-Key": "abc-123"}
    first = await client.post(
        "/api/v1/agent/actions", headers=headers, json={"conversation_id": conversation_id}
    )
    second = await client.post(
        "/api/v1/agent/actions", headers=headers, json={"conversation_id": conversation_id}
    )
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]


async def test_explicit_text_and_listing(client):
    conversation_id = await _create_conversation(client, "suggest")
    created = await client.post(
        "/api/v1/agent/actions",
        headers=TOKEN_HEADER,
        json={"conversation_id": conversation_id, "text": "Привет!", "generate": False},
    )
    assert created.status_code == 201
    assert created.json()["text"] == "Привет!"

    listed = await client.get(
        "/api/v1/agent/actions?status=pending", headers=TOKEN_HEADER
    )
    assert listed.status_code == 200
    assert all(item["status"] == "pending" for item in listed.json())
    assert any(item["text"] == "Привет!" for item in listed.json())


async def test_create_action_for_foreign_conversation_404(client):
    response = await client.post(
        "/api/v1/agent/actions",
        headers={"X-Match-Token": "other-user"},
        json={"conversation_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 404
