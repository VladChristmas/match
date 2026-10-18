import pytest

from app.api.ratelimit import reset_rate_limit
from app.config import get_settings

TOKEN_HEADER = {"X-Match-Token": "rate-limited-user"}
OTHER_HEADER = {"X-Match-Token": "other-rate-limited-user"}


@pytest.fixture(autouse=True)
def rate_limited(monkeypatch):
    monkeypatch.setenv("MATCH_RATE_LIMIT_PER_MINUTE", "2")
    get_settings.cache_clear()
    reset_rate_limit()
    yield
    get_settings.cache_clear()
    reset_rate_limit()


@pytest.fixture
def db_backend(monkeypatch):
    monkeypatch.setenv("MATCH_RATE_LIMIT_BACKEND", "db")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def _draft_statuses(client, header, count=3):
    created = await client.post("/api/v1/conversations", headers=header, json={})
    url = f"/api/v1/conversations/{created.json()['id']}/drafts"
    return [(await client.post(url, headers=header)).status_code for _ in range(count)]


async def test_draft_rate_limit(client):
    created = await client.post("/api/v1/conversations", headers=TOKEN_HEADER, json={})
    conversation_id = created.json()["id"]
    url = f"/api/v1/conversations/{conversation_id}/drafts"

    first = await client.post(url, headers=TOKEN_HEADER)
    second = await client.post(url, headers=TOKEN_HEADER)
    third = await client.post(url, headers=TOKEN_HEADER)

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert third.json()["detail"] == "Rate limit exceeded"


async def test_agent_action_rate_limit(client):
    created = await client.post("/api/v1/conversations", headers=TOKEN_HEADER, json={})
    conversation_id = created.json()["id"]
    payload = {"conversation_id": conversation_id, "text": "hi", "generate": False}
    url = "/api/v1/agent/actions"

    first = await client.post(url, headers=TOKEN_HEADER, json=payload)
    second = await client.post(url, headers=TOKEN_HEADER, json=payload)
    third = await client.post(url, headers=TOKEN_HEADER, json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert third.status_code == 429


async def test_db_backend_limits_per_user(client, db_backend, engine):
    created = await client.post("/api/v1/conversations", headers=TOKEN_HEADER, json={})
    url = f"/api/v1/conversations/{created.json()['id']}/drafts"

    hits = [(await client.post(url, headers=TOKEN_HEADER)).status_code for _ in range(3)]
    assert hits == [200, 200, 429]

    from sqlalchemy import select

    from app.models import RateLimitCounter

    async with engine.connect() as conn:
        rows = list(await conn.execute(select(RateLimitCounter.count)))
    assert [row[0] for row in rows] == [2]


async def test_db_backend_is_isolated_between_users(client, db_backend):
    assert await _draft_statuses(client, TOKEN_HEADER) == [200, 200, 429]
    assert await _draft_statuses(client, OTHER_HEADER) == [200, 200, 429]
