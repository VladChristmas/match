"""Integration adapter contract (Этап 7).

Агент не подключается к площадкам напрямую (ADR-0004/ADR-0008): он наблюдает экран.
Поэтому единственная разрешённая «интеграция» — ручной импорт сообщений. Всё остальное
описывается как `unsupported`, чтобы не имитировать реальное подключение (roadmap, Этап 7).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable


class IntegrationStatus(StrEnum):
    AVAILABLE = "available"
    UNSUPPORTED = "unsupported"
    NOT_AUTHORIZED = "not_authorized"
    DISCONNECTED = "disconnected"


@dataclass(frozen=True)
class IntegrationCapabilities:
    supported: bool = False
    manual_import: bool = False
    screen_observation: bool = False
    direct_messaging: bool = False
    auto_send: bool = False
    requires_authorization: bool = False


@runtime_checkable
class IntegrationAdapter(Protocol):
    """Контракт адаптера интеграции. Проверяется contract-тестами."""

    platform_id: str
    display_name: str
    capabilities: IntegrationCapabilities

    def status(self) -> IntegrationStatus: ...

    def disconnect(self) -> IntegrationStatus: ...
