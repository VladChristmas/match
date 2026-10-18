TOKEN_HEADER = {"X-Match-Token": "privacy-user"}


async def test_export_requires_token(client):
    response = await client.get("/api/v1/privacy/export")
    assert response.status_code == 401


async def test_export_contains_created_data(client):
    await client.patch("/api/v1/profile", headers=TOKEN_HEADER, json={"relationship_goals": ["x"]})
    created = await client.post("/api/v1/conversations", headers=TOKEN_HEADER, json={})
    conversation_id = created.json()["id"]
    await client.post(
        f"/api/v1/conversations/{conversation_id}/messages/import",
        headers=TOKEN_HEADER,
        json={"content": "hi"},
    )

    response = await client.get("/api/v1/privacy/export", headers=TOKEN_HEADER)
    assert response.status_code == 200
    body = response.json()
    assert body["profile"]["relationship_goals"] == ["x"]
    assert body["user"]["token_ref"] == "redacted"
    assert len(body["conversations"]) == 1
    assert body["conversations"][0]["messages"][0]["content"] == "hi"


async def test_deletion_removes_all_data(client):
    created = await client.post("/api/v1/conversations", headers=TOKEN_HEADER, json={})
    conversation_id = created.json()["id"]
    await client.post(
        f"/api/v1/conversations/{conversation_id}/messages/import",
        headers=TOKEN_HEADER,
        json={"content": "bye"},
    )

    deleted = await client.post("/api/v1/privacy/deletion-request", headers=TOKEN_HEADER)
    assert deleted.status_code == 204

    listed = await client.get("/api/v1/conversations", headers=TOKEN_HEADER)
    assert listed.json() == []
    export = await client.get("/api/v1/privacy/export", headers=TOKEN_HEADER)
    assert export.json()["conversations"] == []


async def test_deletion_is_isolated_per_user(client):
    mine = await client.post("/api/v1/conversations", headers=TOKEN_HEADER, json={})
    assert mine.status_code == 201
    other = await client.post(
        "/api/v1/conversations", headers={"X-Match-Token": "other-user"}, json={}
    )
    assert other.status_code == 201

    await client.post("/api/v1/privacy/deletion-request", headers=TOKEN_HEADER)

    kept = await client.get("/api/v1/conversations", headers={"X-Match-Token": "other-user"})
    assert len(kept.json()) == 1
