from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, RegistryDep
from app.integrations.base import IntegrationAdapter
from app.schemas import IntegrationCapabilitiesRead, IntegrationRead

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])


def _serialize(adapter: IntegrationAdapter) -> IntegrationRead:
    return IntegrationRead(
        platform_id=adapter.platform_id,
        display_name=adapter.display_name,
        status=adapter.status().value,
        capabilities=IntegrationCapabilitiesRead.model_validate(adapter.capabilities),
    )


def _get(registry: RegistryDep, platform_id: str) -> IntegrationAdapter:
    adapter = registry.get(platform_id)
    if adapter is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown platform",
        )
    return adapter


@router.get("", response_model=list[IntegrationRead])
async def list_integrations(registry: RegistryDep, user: CurrentUser) -> list[IntegrationRead]:
    return [_serialize(adapter) for adapter in registry.list()]


@router.get("/{platform_id}/capabilities", response_model=IntegrationCapabilitiesRead)
async def get_capabilities(
    platform_id: str, registry: RegistryDep, user: CurrentUser
) -> IntegrationCapabilitiesRead:
    adapter = _get(registry, platform_id)
    return IntegrationCapabilitiesRead.model_validate(adapter.capabilities)


@router.get("/{platform_id}/status", response_model=IntegrationRead)
async def get_status(platform_id: str, registry: RegistryDep, user: CurrentUser) -> IntegrationRead:
    return _serialize(_get(registry, platform_id))


@router.post("/{platform_id}/disconnect", response_model=IntegrationRead)
async def disconnect(platform_id: str, registry: RegistryDep, user: CurrentUser) -> IntegrationRead:
    adapter = _get(registry, platform_id)
    if not adapter.capabilities.supported:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Integration is unsupported",
        )
    adapter.disconnect()
    return _serialize(adapter)
