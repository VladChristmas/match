from functools import lru_cache

from app.integrations.base import IntegrationAdapter
from app.integrations.manual_import import ManualImportAdapter
from app.integrations.unsupported import UnsupportedAdapter

# Известные площадки, интеграцию с которыми мы явно не поддерживаем.
UNSUPPORTED_PLATFORMS: dict[str, str] = {
    "tinder": "Tinder",
    "badoo": "Badoo",
    "bumble": "Bumble",
    "okcupid": "OkCupid",
    "hinge": "Hinge",
    "mamba": "Мамба",
}


class IntegrationRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, IntegrationAdapter] = {}
        self.register(ManualImportAdapter())
        for platform_id, display_name in UNSUPPORTED_PLATFORMS.items():
            self.register(UnsupportedAdapter(platform_id, display_name))

    def register(self, adapter: IntegrationAdapter) -> None:
        self._adapters[adapter.platform_id] = adapter

    def get(self, platform_id: str) -> IntegrationAdapter | None:
        return self._adapters.get(platform_id)

    def list(self) -> list[IntegrationAdapter]:
        return list(self._adapters.values())


@lru_cache
def get_registry() -> IntegrationRegistry:
    return IntegrationRegistry()
