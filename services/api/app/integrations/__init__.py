from app.integrations.base import IntegrationAdapter, IntegrationCapabilities, IntegrationStatus
from app.integrations.manual_import import ManualImportAdapter
from app.integrations.registry import (
    UNSUPPORTED_PLATFORMS,
    IntegrationRegistry,
    get_registry,
)
from app.integrations.unsupported import UnsupportedAdapter

__all__ = [
    "IntegrationAdapter",
    "IntegrationCapabilities",
    "IntegrationStatus",
    "IntegrationRegistry",
    "ManualImportAdapter",
    "UnsupportedAdapter",
    "UNSUPPORTED_PLATFORMS",
    "get_registry",
]
