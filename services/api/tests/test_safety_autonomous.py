"""Сквозные сценарии безопасности автоотправки (аудит 2026-10-25, P0-2).

Полный путь через реальное API: знакомство в режиме `auto_send` → входящие
сообщения → решение/действие. Проверяем, что опасные ситуации НЕ доходят до
автономной отправки, а повтор после сбоя не создаёт дублей.
"""

TOKEN = {"X-Match-Token": "safety-user"}

FINANCIAL_TEXT = "Срочно переведи деньги на биткоин кошелёк"
PERSONAL_DATA_TEXT = "Пришли номер карты и код из смс для подтверждения"
BOUNDARIES_TEXT = "Давай только мы, официально"


async def _conversation(client, mode: str = "auto_send") -> str:
    response = await client.post(
        "/api/v1/conversations", headers=TOKEN, json={"autonomy_mode": mode}
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _import(client, conversation_id: str, content: str) -> None:
    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/messages/import",
        headers=TOKEN,
        json={"content": content, "direction": "inbound"},
    )
    assert response.status_code == 201


async def test_financial_request_never_auto_sends(client):
    """Просьба о деньгах: стоп-фактор — действие только на подтверждение."""
    conversation_id = await _conversation(client)
    await _import(client, conversation_id, FINANCIAL_TEXT)
    created = await client.post(
        "/api/v1/agent/actions",
        headers=TOKEN,
        json={
            "conversation_id": conversation_id,
            "text": "конечно, сейчас переведу",
            "generate": False,
        },
    )
    assert created.status_code == 201
    assert created.json()["status"] == "pending"  # не delivered


async def test_personal_data_request_never_auto_sends(client):
    """Запрос личных данных: стоп-фактор — действие только на подтверждение."""
    conversation_id = await _conversation(client)
    await _import(client, conversation_id, PERSONAL_DATA_TEXT)
    created = await client.post(
        "/api/v1/agent/actions",
        headers=TOKEN,
        json={"conversation_id": conversation_id, "text": "вот мои данные", "generate": False},
    )
    assert created.status_code == 201
    assert created.json()["status"] == "pending"


async def test_commitment_intent_escalates_to_user(client):
    """Чувства/границы/обязательства: решение переходит пользователю."""
    conversation_id = await _conversation(client)
    await _import(client, conversation_id, BOUNDARIES_TEXT)
    evaluated = await client.post(
        "/api/v1/agent/decisions/evaluate",
        headers=TOKEN,
        json={"conversation_id": conversation_id, "trigger_text": BOUNDARIES_TEXT},
    )
    assert evaluated.status_code == 200
    body = evaluated.json()
    assert body["mode"] == "escalate"
    assert body["escalation_reason"] == "sensitive_intent"


async def test_ambiguous_conversation_requires_confirmation(client):
    """Неоднозначная переписка без ясного сигнала: автономный запуск запрещён."""
    conversation_id = await _conversation(client)
    for text in ("ага", "не знаю", "мб"):
        await _import(client, conversation_id, text)
    evaluated = await client.post(
        "/api/v1/agent/decisions/evaluate",
        headers=TOKEN,
        json={"conversation_id": conversation_id},
    )
    assert evaluated.status_code == 200
    body = evaluated.json()
    assert body["mode"] != "execute"  # хотя бы verify/escalate, но не авто-исполнение
    assert body["action"] in ("wait", "ask_clarifying", "escalate_to_user", "no_op")


async def test_paused_queue_requires_confirmation(client):
    """Глобальная пауза: автоотправка выключена независимо от настроек знакомства."""
    conversation_id = await _conversation(client)
    await _import(client, conversation_id, "Привет! Как дела?")
    pause = await client.post("/api/v1/agent/pause", headers=TOKEN)
    assert pause.status_code in (200, 409)  # 409 — уже была пауза ранее
    try:
        evaluated = await client.post(
            "/api/v1/agent/decisions/evaluate",
            headers=TOKEN,
            json={"conversation_id": conversation_id},
        )
        assert evaluated.status_code == 200
        assert evaluated.json()["mode"] != "execute"
    finally:
        await client.post("/api/v1/agent/resume", headers=TOKEN)


async def test_retry_after_failure_creates_no_duplicate(client):
    """Повторная отправка после сбоя с тем же ключом идемпотентности — без дубля."""
    conversation_id = await _conversation(client)
    await _import(client, conversation_id, "Привет! Как дела?")
    headers = {**TOKEN, "Idempotency-Key": "safety-retry-1"}
    payload = {
        "conversation_id": conversation_id,
        "text": "Привет! Нормально, а у тебя?",
        "generate": False,
    }
    first = await client.post("/api/v1/agent/actions", headers=headers, json=payload)
    retry = await client.post("/api/v1/agent/actions", headers=headers, json=payload)
    assert first.status_code == 201
    assert retry.status_code == 200  # повтор распознан, новый ресурс не создан
    assert first.json()["id"] == retry.json()["id"]
    listing = await client.get(
        "/api/v1/agent/actions", headers=TOKEN, params={"conversation_id": conversation_id}
    )
    matches = [a for a in listing.json() if a["id"] == first.json()["id"]]
    assert len(matches) == 1
