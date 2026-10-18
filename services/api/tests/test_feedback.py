TOKEN_HEADER = {"X-Match-Token": "feedback-token"}


async def test_create_feedback(client):
    response = await client.post(
        "/api/v1/feedback",
        headers=TOKEN_HEADER,
        json={"feedback_type": "rating", "rating": 5, "correction": "great tone"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["feedback_type"] == "rating"
    assert body["rating"] == 5
    assert body["correction"] == "great tone"
    assert body["user_id"]


async def test_rating_out_of_range_is_rejected(client):
    response = await client.post(
        "/api/v1/feedback",
        headers=TOKEN_HEADER,
        json={"feedback_type": "rating", "rating": 9},
    )
    assert response.status_code == 422


async def test_feedback_requires_token(client):
    response = await client.post("/api/v1/feedback", json={"feedback_type": "rating", "rating": 4})
    assert response.status_code == 401


async def test_list_feedback_is_isolated_per_token(client):
    await client.post(
        "/api/v1/feedback",
        headers=TOKEN_HEADER,
        json={"feedback_type": "thumbs_up"},
    )
    await client.post(
        "/api/v1/feedback",
        headers={"X-Match-Token": "other-token"},
        json={"feedback_type": "thumbs_down"},
    )

    listed = await client.get("/api/v1/feedback", headers=TOKEN_HEADER)
    assert listed.status_code == 200
    body = listed.json()
    assert len(body) == 1
    assert body[0]["feedback_type"] == "thumbs_up"
