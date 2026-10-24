import uuid

from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import app

PROBE_PATH = "/api/v1/observability-probe"


def test_cors_defaults_to_wildcard_in_development():
    assert Settings(environment="development").cors_allow_origins == ["*"]


def test_cors_uses_explicit_origins_in_any_environment():
    settings = Settings(
        environment="production",
        cors_origins="https://match.example, https://admin.match.example",
    )
    assert settings.cors_allow_origins == [
        "https://match.example",
        "https://admin.match.example",
    ]


def test_cors_blocks_cross_origin_in_production_when_list_empty():
    assert Settings(environment="production").cors_allow_origins == []


async def test_response_has_generated_request_id(client):
    response = await client.get("/")
    assert response.status_code == 200
    uuid.UUID(response.headers["x-request-id"])


async def test_provided_request_id_is_echoed(client):
    response = await client.get("/", headers={"x-request-id": "req-e2e-001"})
    assert response.status_code == 200
    assert response.headers["x-request-id"] == "req-e2e-001"


async def test_cors_preflight_allows_origin_in_development(client):
    response = await client.options(
        "/api/v1/profile",
        headers={
            "Origin": "http://localhost:1420",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] in (
        "*",
        "http://localhost:1420",
    )


async def test_unhandled_exception_returns_generic_500():
    @app.get(PROBE_PATH)
    async def _boom() -> dict[str, str]:
        raise RuntimeError("boom")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(PROBE_PATH)
    app.routes[:] = [r for r in app.routes if getattr(r, "path", None) != PROBE_PATH]

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert response.headers["x-request-id"]
