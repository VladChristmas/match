"""Тесты статуса LLM-шлюза (`GET /api/v1/llm/status`, аудит P1-1)."""

from app.config import get_settings

TOKEN_HEADER = {"X-Match-Token": "llm-status-user"}


async def test_status_requires_token(client):
    response = await client.get("/api/v1/llm/status")
    assert response.status_code in (401, 403)


async def test_status_reports_provider_and_limit(client):
    response = await client.get("/api/v1/llm/status", headers=TOKEN_HEADER)
    assert response.status_code == 200
    body = response.json()
    # echo-дефолт в тестовом окружении
    assert body["provider"] == "echo"
    assert body["declared_providers"] == ["echo", "echo"] or "echo" in body["declared_providers"]
    assert isinstance(body["fallback_providers"], list)
    assert isinstance(body["skipped_providers"], list)
    assert body["user_request_limit"] == 0
    assert body["user_request_limit_enabled"] is False


async def test_status_reports_limit_when_enabled(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_user_request_limit", 5)
    response = await client.get("/api/v1/llm/status", headers=TOKEN_HEADER)
    assert response.status_code == 200
    body = response.json()
    assert body["user_request_limit"] == 5
    assert body["user_request_limit_enabled"] is True


async def test_status_lists_skipped_providers_without_keys(client, monkeypatch):
    """openai без ключа объявлен в настройках, но не попадает в рабочий состав."""
    from app.llm.gateway import get_gateway

    settings = get_settings()  # lru_cache-синглтон: патчим атрибуты на нём
    monkeypatch.setattr(settings, "llm_provider", "openai")
    monkeypatch.setattr(settings, "llm_fallback_providers", "echo")
    monkeypatch.setattr(settings, "openai_api_key", "")
    get_gateway.cache_clear()
    try:
        response = await client.get("/api/v1/llm/status", headers=TOKEN_HEADER)
    finally:
        get_gateway.cache_clear()  # вернуть шлюз к дефолтному составу
    assert response.status_code == 200
    body = response.json()
    assert "openai" in body["declared_providers"]
    assert "openai" in body["skipped_providers"]
    assert body["provider"] == "echo"
