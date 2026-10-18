import pytest

from app.integrations import (
    IntegrationAdapter,
    IntegrationCapabilities,
    IntegrationStatus,
    get_registry,
)

TOKEN_HEADER = {"X-Match-Token": "test-token"}


@pytest.fixture(autouse=True)
def fresh_registry():
    get_registry.cache_clear()
    yield
    get_registry.cache_clear()


@pytest.mark.parametrize("adapter", get_registry().list())
def test_adapter_satisfies_contract(adapter):
    assert isinstance(adapter, IntegrationAdapter)
    assert isinstance(adapter.platform_id, str) and adapter.platform_id
    assert isinstance(adapter.display_name, str) and adapter.display_name
    assert isinstance(adapter.capabilities, IntegrationCapabilities)
    assert isinstance(adapter.status(), IntegrationStatus)
    assert isinstance(adapter.disconnect(), IntegrationStatus)
    for field in (
        "supported",
        "manual_import",
        "screen_observation",
        "direct_messaging",
        "auto_send",
        "requires_authorization",
    ):
        assert isinstance(getattr(adapter.capabilities, field), bool)


def test_registry_has_unique_platform_ids():
    ids = [adapter.platform_id for adapter in get_registry().list()]
    assert len(ids) == len(set(ids))


def test_manual_import_is_supported_and_disconnects():
    adapter = get_registry().get("manual_import")
    assert adapter is not None
    assert adapter.capabilities.supported is True
    assert adapter.capabilities.manual_import is True
    assert adapter.capabilities.direct_messaging is False
    assert adapter.status() is IntegrationStatus.AVAILABLE
    assert adapter.disconnect() is IntegrationStatus.DISCONNECTED
    assert adapter.status() is IntegrationStatus.DISCONNECTED


def test_platform_adapters_are_unsupported():
    adapter = get_registry().get("tinder")
    assert adapter is not None
    assert adapter.capabilities.supported is False
    assert adapter.status() is IntegrationStatus.UNSUPPORTED
    assert adapter.disconnect() is IntegrationStatus.UNSUPPORTED


async def test_integrations_requires_token(client):
    response = await client.get("/api/v1/integrations")
    assert response.status_code == 401


async def test_list_integrations(client):
    response = await client.get("/api/v1/integrations", headers=TOKEN_HEADER)
    assert response.status_code == 200
    body = response.json()
    platforms = {item["platform_id"]: item for item in body}
    assert "manual_import" in platforms
    assert platforms["manual_import"]["status"] == "available"
    assert platforms["manual_import"]["capabilities"]["manual_import"] is True
    assert platforms["tinder"]["status"] == "unsupported"
    assert platforms["tinder"]["capabilities"]["supported"] is False


async def test_capabilities_endpoint(client):
    response = await client.get(
        "/api/v1/integrations/manual_import/capabilities", headers=TOKEN_HEADER
    )
    assert response.status_code == 200
    assert response.json()["supported"] is True


async def test_unknown_platform_returns_404(client):
    response = await client.get("/api/v1/integrations/nope/status", headers=TOKEN_HEADER)
    assert response.status_code == 404


async def test_disconnect_supported_integration(client):
    response = await client.post(
        "/api/v1/integrations/manual_import/disconnect", headers=TOKEN_HEADER
    )
    assert response.status_code == 200
    assert response.json()["status"] == "disconnected"


async def test_disconnect_unsupported_integration_conflicts(client):
    response = await client.post("/api/v1/integrations/tinder/disconnect", headers=TOKEN_HEADER)
    assert response.status_code == 409
