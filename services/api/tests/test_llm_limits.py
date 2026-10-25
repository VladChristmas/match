from app.config import get_settings
from app.llm.base import LLMRequest, LLMResponse
from app.llm.gateway import LLMGateway, get_gateway
from app.llm.limits import is_limit_reached
from app.main import app

TOKEN_HEADER = {"X-Match-Token": "limit-token"}


class NamedProvider:
    """Провайдер с управляемым именем — для сценариев выбора/смены провайдера."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.model = name

    async def generate(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            text="ok", provider=self.name, model=self.model, latency_ms=0
        )


class FailingProvider:
    name = "failing"
    model = "failing"

    async def generate(self, request: LLMRequest) -> LLMResponse:
        raise RuntimeError("boom")


async def _new_conversation(client) -> str:
    response = await client.post("/api/v1/conversations", headers=TOKEN_HEADER, json={})
    return response.json()["id"]


async def test_draft_enforces_per_user_limit(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_user_request_limit", 2)
    conversation_id = await _new_conversation(client)

    first = await client.post(
        f"/api/v1/conversations/{conversation_id}/drafts", headers=TOKEN_HEADER
    )
    second = await client.post(
        f"/api/v1/conversations/{conversation_id}/drafts", headers=TOKEN_HEADER
    )
    third = await client.post(
        f"/api/v1/conversations/{conversation_id}/drafts", headers=TOKEN_HEADER
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429


def test_is_limit_reached_boundaries():
    assert is_limit_reached(1, 2) is False          # запас ещё есть
    assert is_limit_reached(2, 2) is True           # достигнут
    assert is_limit_reached(9, 2) is True           # превышен
    assert is_limit_reached(0, 2) is False          # ничего не потрачено
    assert is_limit_reached(100, 0) is False        # 0 = лимит выключен


def test_limit_read_from_env_variable(monkeypatch):
    """MATCH_LLM_USER_REQUEST_LIMIT читается настройками (env_prefix MATCH_)."""
    monkeypatch.setenv("MATCH_LLM_USER_REQUEST_LIMIT", "7")
    get_settings.cache_clear()
    try:
        assert get_settings().llm_user_request_limit == 7
    finally:
        get_settings.cache_clear()


async def test_limit_shared_across_providers(client, monkeypatch):
    """Счётчик лимита общий для пользователя: смена провайдера его не сбрасывает."""
    monkeypatch.setattr(get_settings(), "llm_user_request_limit", 2)
    conversation_id = await _new_conversation(client)

    app.dependency_overrides[get_gateway] = lambda: LLMGateway([NamedProvider("alpha")])
    try:
        first = await client.post(
            f"/api/v1/conversations/{conversation_id}/drafts", headers=TOKEN_HEADER
        )
        second = await client.post(
            f"/api/v1/conversations/{conversation_id}/drafts", headers=TOKEN_HEADER
        )
        # Пользователь переключает провайдера в настройках — лимит сохраняется.
        app.dependency_overrides[get_gateway] = lambda: LLMGateway([NamedProvider("beta")])
        third = await client.post(
            f"/api/v1/conversations/{conversation_id}/drafts", headers=TOKEN_HEADER
        )
    finally:
        app.dependency_overrides.pop(get_gateway, None)
    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429


async def test_draft_returns_503_when_no_provider(client):
    conversation_id = await _new_conversation(client)
    app.dependency_overrides[get_gateway] = lambda: LLMGateway([FailingProvider()])
    try:
        response = await client.post(
            f"/api/v1/conversations/{conversation_id}/drafts", headers=TOKEN_HEADER
        )
    finally:
        app.dependency_overrides.pop(get_gateway, None)
    assert response.status_code == 503
