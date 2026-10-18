from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.auth.service import hash_token
from app.config import get_settings
from app.models import AccessToken

LEGACY_HEADER = {"X-Match-Token": "bootstrap-user"}


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _issue(client, label: str = "test") -> dict:
    response = await client.post(
        "/api/v1/tokens", headers=LEGACY_HEADER, json={"label": label}
    )
    assert response.status_code == 201
    return response.json()


async def test_issue_requires_auth(client):
    assert (await client.post("/api/v1/tokens", json={"label": "x"})).status_code == 401


async def test_issued_token_authenticates(client, engine):
    issued = await _issue(client)
    assert issued["token"].startswith("match_")

    profile = await client.get("/api/v1/profile", headers=bearer(issued["token"]))
    assert profile.status_code == 200

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        stored = list(await session.scalars(select(AccessToken)))
    assert len(stored) == 1
    assert stored[0].token_hash == hash_token(issued["token"])
    assert stored[0].token_hash != issued["token"]
    assert issued["token"] not in stored[0].token_hash


async def test_list_hides_secrets(client):
    await _issue(client)
    response = await client.get("/api/v1/tokens", headers=LEGACY_HEADER)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert "token" not in body[0]
    assert "token_hash" not in body[0]
    assert body[0]["label"] == "test"


async def test_rotate_revokes_old_token(client):
    issued = await _issue(client, label="rotate-me")
    rotated = await client.post(
        f"/api/v1/tokens/{issued['id']}/rotate", headers=LEGACY_HEADER
    )
    assert rotated.status_code == 200
    new_token = rotated.json()["token"]
    assert new_token != issued["token"]

    assert (
        await client.get("/api/v1/profile", headers=bearer(issued["token"]))
    ).status_code == 401
    assert (
        await client.get("/api/v1/profile", headers=bearer(new_token))
    ).status_code == 200

    again = await client.post(
        f"/api/v1/tokens/{issued['id']}/rotate", headers=LEGACY_HEADER
    )
    assert again.status_code == 409


async def test_revoke_blocks_token(client):
    issued = await _issue(client, label="revoke-me")
    assert (
        await client.delete(f"/api/v1/tokens/{issued['id']}", headers=LEGACY_HEADER)
    ).status_code == 204
    assert (
        await client.get("/api/v1/profile", headers=bearer(issued["token"]))
    ).status_code == 401


async def test_token_is_isolated_per_user(client):
    issued = await _issue(client, label="mine")
    other = {"X-Match-Token": "other-user"}
    assert (
        await client.post(f"/api/v1/tokens/{issued['id']}/rotate", headers=other)
    ).status_code == 404
    assert (
        await client.delete(f"/api/v1/tokens/{issued['id']}", headers=other)
    ).status_code == 404
    assert (
        await client.get("/api/v1/profile", headers=bearer(issued["token"]))
    ).status_code == 200


async def test_legacy_tokens_can_be_disabled(client, monkeypatch):
    issued = await _issue(client)
    monkeypatch.setenv("MATCH_AUTH_ALLOW_LEGACY_TOKENS", "false")
    get_settings.cache_clear()
    try:
        legacy = await client.get("/api/v1/profile", headers=LEGACY_HEADER)
        real = await client.get("/api/v1/profile", headers=bearer(issued["token"]))
    finally:
        get_settings.cache_clear()

    assert legacy.status_code == 401
    assert real.status_code == 200
