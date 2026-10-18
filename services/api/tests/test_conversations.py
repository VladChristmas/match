TOKEN_HEADER = {"X-Match-Token": "conv-token"}
OTHER_HEADER = {"X-Match-Token": "conv-token-other"}


async def _create_conversation(client, headers=TOKEN_HEADER):
    response = await client.post("/api/v1/conversations", headers=headers, json={})
    assert response.status_code == 201
    return response.json()


async def test_conversations_require_token(client):
    response = await client.post("/api/v1/conversations", json={})
    assert response.status_code == 401


async def test_create_and_list_conversations(client):
    created = await _create_conversation(client)
    assert created["status"] == "active"
    assert created["autonomy_mode"] == "auto_send"

    listed = await client.get("/api/v1/conversations", headers=TOKEN_HEADER)
    assert listed.status_code == 200
    assert [c["id"] for c in listed.json()] == [created["id"]]


async def test_conversation_is_isolated_between_users(client):
    created = await _create_conversation(client, TOKEN_HEADER)
    foreign = await client.get(f"/api/v1/conversations/{created['id']}", headers=OTHER_HEADER)
    assert foreign.status_code == 404


async def test_import_message_and_list(client):
    conversation = await _create_conversation(client)
    imported = await client.post(
        f"/api/v1/conversations/{conversation['id']}/messages/import",
        headers=TOKEN_HEADER,
        json={"content": "Привет, как дела?", "direction": "inbound"},
    )
    assert imported.status_code == 201
    assert imported.json()["processing_status"] == "received"

    listed = await client.get(
        f"/api/v1/conversations/{conversation['id']}/messages", headers=TOKEN_HEADER
    )
    assert listed.status_code == 200
    assert [m["content"] for m in listed.json()] == ["Привет, как дела?"]


async def test_import_rejects_invalid_direction(client):
    conversation = await _create_conversation(client)
    response = await client.post(
        f"/api/v1/conversations/{conversation['id']}/messages/import",
        headers=TOKEN_HEADER,
        json={"content": "hi", "direction": "sideways"},
    )
    assert response.status_code == 422


async def test_draft_uses_echo_provider_and_history(client):
    conversation = await _create_conversation(client)
    await client.post(
        f"/api/v1/conversations/{conversation['id']}/messages/import",
        headers=TOKEN_HEADER,
        json={"content": "Привет", "direction": "inbound"},
    )
    response = await client.post(
        f"/api/v1/conversations/{conversation['id']}/drafts", headers=TOKEN_HEADER
    )
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "echo"
    assert body["text"] == "Эхо: Привет"
    assert body["validation_ok"] is True


async def test_draft_on_foreign_conversation_is_not_found(client):
    conversation = await _create_conversation(client, TOKEN_HEADER)
    response = await client.post(
        f"/api/v1/conversations/{conversation['id']}/drafts", headers=OTHER_HEADER
    )
    assert response.status_code == 404
