TOKEN_HEADER = {"X-Match-Token": "analysis-token"}
OTHER_HEADER = {"X-Match-Token": "analysis-token-other"}


async def test_analysis_requires_token(client):
    response = await client.post("/api/v1/analysis/compatibility", json={})
    assert response.status_code == 401


async def test_compatibility_uses_profile_and_counterpart(client):
    await client.patch(
        "/api/v1/profile",
        headers=TOKEN_HEADER,
        json={
            "relationship_goals": ["семья", "путешествия"],
            "values": ["честность"],
        },
    )
    response = await client.post(
        "/api/v1/analysis/compatibility",
        headers=TOKEN_HEADER,
        json={"counterpart": {"goals": ["семья"], "values": ["честность"]}},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["goals_alignment"] == 0.5
    assert body["values_alignment"] == 1.0
    assert body["reciprocity"] == 0.5
    assert body["uncertainty"] == 0.33

    listed = await client.get("/api/v1/analysis/compatibility", headers=TOKEN_HEADER)
    assert [item["id"] for item in listed.json()] == [body["id"]]


async def test_compatibility_is_isolated_between_users(client):
    await client.post(
        "/api/v1/analysis/compatibility", headers=TOKEN_HEADER, json={}
    )
    listed = await client.get("/api/v1/analysis/compatibility", headers=OTHER_HEADER)
    assert listed.json() == []


async def test_risk_from_conversation_messages(client):
    conversation = (
        await client.post("/api/v1/conversations", headers=TOKEN_HEADER, json={})
    ).json()
    await client.post(
        f"/api/v1/conversations/{conversation['id']}/messages/import",
        headers=TOKEN_HEADER,
        json={"content": "Срочно переведи деньги на карту", "direction": "inbound"},
    )
    response = await client.post(
        "/api/v1/analysis/risk",
        headers=TOKEN_HEADER,
        json={"conversation_id": conversation["id"]},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["risk_category"] == "financial_request"
    assert body["recommended_action"] == "warn_and_pause"
    assert body["confidence"] > 0
    assert any(signal["category"] == "financial_request" for signal in body["signals"])


async def test_risk_on_foreign_conversation_is_not_found(client):
    conversation = (
        await client.post("/api/v1/conversations", headers=TOKEN_HEADER, json={})
    ).json()
    response = await client.post(
        "/api/v1/analysis/risk",
        headers=OTHER_HEADER,
        json={"conversation_id": conversation["id"]},
    )
    assert response.status_code == 404
