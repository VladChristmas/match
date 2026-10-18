import pytest

from app.config import get_settings

ADMIN_HEADER = {"X-Match-Token": "admin-user"}
USER_HEADER = {"X-Match-Token": "regular-user"}


@pytest.fixture
def admin_configured(monkeypatch):
    monkeypatch.setenv("MATCH_ADMIN_TOKEN_REFS", "admin-user")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def test_metrics_requires_token(client):
    assert (await client.get("/api/v1/admin/metrics")).status_code == 401


async def test_metrics_forbidden_for_regular_user(client):
    response = await client.get("/api/v1/admin/metrics", headers=USER_HEADER)
    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access required"


async def test_metrics_forbidden_when_admin_not_configured(client):
    assert (await client.get("/api/v1/admin/metrics", headers=ADMIN_HEADER)).status_code == 403


async def test_admin_is_promoted_and_sees_metrics(client, admin_configured):
    created = await client.post("/api/v1/conversations", headers=USER_HEADER, json={})
    conversation_id = created.json()["id"]
    await client.post(
        f"/api/v1/conversations/{conversation_id}/messages/import",
        headers=USER_HEADER,
        json={"content": "hi"},
    )

    whoami = await client.get("/api/v1/admin/whoami", headers=ADMIN_HEADER)
    assert whoami.status_code == 200
    assert whoami.json()["role"] == "admin"

    response = await client.get("/api/v1/admin/metrics", headers=ADMIN_HEADER)
    assert response.status_code == 200
    body = response.json()

    assert body["users"]["total"] >= 2
    assert body["users"]["by_key"]["admin"] >= 1
    assert body["conversations"]["total"] == 1
    assert body["messages"]["total"] == 1
    assert body["messages"]["by_key"]["received"] == 1
    assert body["access_tokens"]["total"] == 0
    assert body["settings"]["rate_limit_backend"] in {"memory", "db"}
    assert body["settings"]["admin_configured"] == "true"


async def test_metrics_contain_no_personal_content(client, admin_configured):
    created = await client.post("/api/v1/conversations", headers=USER_HEADER, json={})
    conversation_id = created.json()["id"]
    await client.post(
        f"/api/v1/conversations/{conversation_id}/messages/import",
        headers=USER_HEADER,
        json={"content": "секретный текст"},
    )

    raw = (await client.get("/api/v1/admin/metrics", headers=ADMIN_HEADER)).text
    assert "секретный текст" not in raw
    assert "regular-user" not in raw
    assert "token_ref" not in raw


async def test_regular_user_role_stays_user(client, admin_configured):
    await client.get("/api/v1/profile", headers=USER_HEADER)
    assert (await client.get("/api/v1/admin/whoami", headers=USER_HEADER)).status_code == 403
