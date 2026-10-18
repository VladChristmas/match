from app.config import get_settings
from app.llm.base import LLMRequest, LLMResponse
from app.llm.gateway import LLMGateway, get_gateway
from app.main import app

TOKEN_HEADER = {"X-Match-Token": "limit-token"}


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
