"""Тесты адаптивной автономности и калибровки (Этап 26, ADR-0032)."""

TOKEN_HEADER = {"X-Match-Token": "autonomy-user"}


async def _create_conversation(client, autonomy_mode="auto_send"):
    response = await client.post(
        "/api/v1/conversations",
        headers=TOKEN_HEADER,
        json={"autonomy_mode": autonomy_mode},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_action(client, conversation_id, generate=False, text=None):
    payload = {"conversation_id": conversation_id, "generate": generate}
    if text is not None:
        payload["text"] = text
        payload["generate"] = False
    response = await client.post(
        "/api/v1/agent/actions",
        headers=TOKEN_HEADER,
        json=payload,
    )
    assert response.status_code == 201
    return response.json()


async def test_budget_defaults(client):
    response = await client.get("/api/v1/autonomy/budget", headers=TOKEN_HEADER)
    assert response.status_code == 200
    body = response.json()
    assert body["max_messages_per_day"] == 50
    assert body["active_start_hour"] == 0
    assert body["active_end_hour"] == 24
    assert body["auto_stop_after_errors"] == 3
    assert body["consecutive_errors"] == 0
    assert body["global_paused"] is False


async def test_update_budget(client):
    updated = await client.patch(
        "/api/v1/autonomy/budget",
        headers=TOKEN_HEADER,
        json={
            "max_messages_per_day": 10,
            "global_paused": True,
            "auto_stop_after_errors": 2,
        },
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["max_messages_per_day"] == 10
    assert body["global_paused"] is True
    assert body["auto_stop_after_errors"] == 2


async def test_global_paused_blocks_autonomous_delivery(client):
    conversation_id = await _create_conversation(client)
    await client.patch(
        "/api/v1/autonomy/budget",
        headers=TOKEN_HEADER,
        json={"global_paused": True},
    )

    created = await _create_action(client, conversation_id, generate=True)
    assert created["status"] == "pending"


async def test_resume_allows_delivery(client):
    conversation_id = await _create_conversation(client)
    await client.patch(
        "/api/v1/autonomy/budget",
        headers=TOKEN_HEADER,
        json={"global_paused": True},
    )
    await client.patch(
        "/api/v1/autonomy/budget",
        headers=TOKEN_HEADER,
        json={"global_paused": False},
    )

    created = await _create_action(client, conversation_id, generate=True)
    assert created["status"] == "sent"


async def test_record_error_and_auto_stop(client):
    conversation_id = await _create_conversation(client, autonomy_mode="suggest")

    # Создаём действие и отменяем его (ошибка)
    created = await _create_action(client, conversation_id, text="Тест", generate=False)
    action_id = created["id"]

    rejected = await client.post(
        f"/api/v1/agent/actions/{action_id}/reject",
        headers=TOKEN_HEADER,
    )
    assert rejected.status_code == 200

    # Проверяем счётчик ошибок в бюджете
    budget = await client.get("/api/v1/autonomy/budget", headers=TOKEN_HEADER)
    assert budget.json()["consecutive_errors"] == 1

    # Журнал ошибок
    errors = await client.get("/api/v1/autonomy/errors", headers=TOKEN_HEADER)
    assert errors.status_code == 200
    assert len(errors.json()) >= 1
    assert errors.json()[0]["error_type"] == "rejected"


async def test_reset_errors(client):
    conversation_id = await _create_conversation(client, autonomy_mode="suggest")
    created = await _create_action(client, conversation_id, text="Тест", generate=False)
    await client.post(
        f"/api/v1/agent/actions/{created['id']}/reject",
        headers=TOKEN_HEADER,
    )

    budget = await client.get("/api/v1/autonomy/budget", headers=TOKEN_HEADER)
    assert budget.json()["consecutive_errors"] == 1

    reset = await client.post("/api/v1/autonomy/reset-errors", headers=TOKEN_HEADER)
    assert reset.status_code == 200
    assert reset.json()["consecutive_errors"] == 0


async def test_auto_stop_after_errors(client):
    conversation_id = await _create_conversation(client, autonomy_mode="suggest")
    await client.patch(
        "/api/v1/autonomy/budget",
        headers=TOKEN_HEADER,
        json={"auto_stop_after_errors": 1},
    )

    # Один отказ → ошибка засчитывается, авто-остановка должна сработать
    created = await _create_action(client, conversation_id, text="Тест", generate=False)
    await client.post(
        f"/api/v1/agent/actions/{created['id']}/reject",
        headers=TOKEN_HEADER,
    )

    budget = await client.get("/api/v1/autonomy/budget", headers=TOKEN_HEADER)
    assert budget.json()["consecutive_errors"] == 1

    # При auto_send следующее действие заблокировано авто-остановкой
    blocked_conversation = await _create_conversation(client, autonomy_mode="auto_send")
    blocked = await _create_action(client, blocked_conversation, generate=True)
    assert blocked["status"] == "pending"


async def test_daily_limit_blocks(client):
    conversation_id = await _create_conversation(client)
    await client.patch(
        "/api/v1/autonomy/budget",
        headers=TOKEN_HEADER,
        json={"max_messages_per_day": 1},
    )

    # Первое действие проходит
    first = await _create_action(client, conversation_id, generate=True)
    assert first["status"] == "sent"

    # Второе блокируется лимитом
    second = await _create_action(client, conversation_id, generate=True)
    assert second["status"] == "pending"


async def test_classify_feedback(client):
    conversation_id = await _create_conversation(client)
    feedback = await client.post(
        "/api/v1/feedback",
        headers=TOKEN_HEADER,
        json={
            "feedback_type": "draft",
            "rating": 2,
            "correction": "Сделай короче",
            "conversation_id": conversation_id,
        },
    )
    assert feedback.status_code in (200, 201)
    feedback_id = feedback.json()["id"]

    classified = await client.post(
        f"/api/v1/autonomy/feedback/{feedback_id}/classify",
        headers=TOKEN_HEADER,
        json={},
    )
    assert classified.status_code == 200
    body = classified.json()
    assert body["classification"] in (
        "factual_error",
        "wrong_tone",
        "wrong_strategy",
        "personal_preference",
    )


async def test_calibration_rules_list(client):
    listed = await client.get("/api/v1/autonomy/calibration-rules", headers=TOKEN_HEADER)
    assert listed.status_code == 200
    assert isinstance(listed.json(), list)


async def test_foreign_user_isolation(client):
    # Создаём бюджет для autonomía-user
    await client.get("/api/v1/autonomy/budget", headers=TOKEN_HEADER)

    # Чужой пользователь не видит его бюджет (создаёт свой)
    other_budget = await client.get(
        "/api/v1/autonomy/budget",
        headers={"X-Match-Token": "other-user"},
    )
    assert other_budget.status_code == 200
    # Это новый бюджет для другого пользователя, ошибок нет
