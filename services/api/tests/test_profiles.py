TOKEN_HEADER = {"X-Match-Token": "test-token"}


async def test_profile_requires_token(client):
    response = await client.get("/api/v1/profile")
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing access token"


async def test_get_profile_creates_default(client):
    response = await client.get("/api/v1/profile", headers=TOKEN_HEADER)
    assert response.status_code == 200
    body = response.json()
    assert body["relationship_goals"] == []
    assert body["values"] == []
    assert body["preferences"] == {}
    assert body["boundaries"] == {}
    assert body["profile_version"] == 1


async def test_patch_profile_updates_fields_and_bumps_version(client):
    created = await client.get("/api/v1/profile", headers=TOKEN_HEADER)
    assert created.status_code == 200

    updated = await client.patch(
        "/api/v1/profile",
        headers=TOKEN_HEADER,
        json={"relationship_goals": ["long-term"], "boundaries": {"smoking": "no"}},
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["relationship_goals"] == ["long-term"]
    assert body["boundaries"] == {"smoking": "no"}
    assert body["values"] == []
    assert body["profile_version"] == 2


async def test_profiles_are_isolated_per_token(client):
    first = await client.get("/api/v1/profile", headers={"X-Match-Token": "user-a"})
    second = await client.get("/api/v1/profile", headers={"X-Match-Token": "user-b"})
    assert first.json()["id"] != second.json()["id"]


async def test_communication_profile_defaults_and_update(client):
    created = await client.get("/api/v1/profile/communication", headers=TOKEN_HEADER)
    assert created.status_code == 200
    assert created.json()["version"] == 1
    assert created.json()["typical_message_length"] is None

    updated = await client.patch(
        "/api/v1/profile/communication",
        headers=TOKEN_HEADER,
        json={"typical_message_length": "short", "tone_preferences": {"warm": True}},
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["typical_message_length"] == "short"
    assert body["tone_preferences"] == {"warm": True}
    assert body["version"] == 2


async def test_bearer_token_is_accepted(client):
    response = await client.get("/api/v1/profile", headers={"Authorization": "Bearer bearer-token"})
    assert response.status_code == 200
