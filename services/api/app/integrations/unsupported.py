from app.integrations.base import IntegrationCapabilities, IntegrationStatus


class UnsupportedAdapter:
    """Адаптер площадки, интеграцию с которой мы не поддерживаем.

    Прямое подключение к площадкам запрещено (ADR-0004). Вместо имитации интеграции
    адаптер всегда сообщает `unsupported` и нулевые возможности.
    """

    def __init__(self, platform_id: str, display_name: str) -> None:
        self.platform_id = platform_id
        self.display_name = display_name
        self.capabilities = IntegrationCapabilities(supported=False)

    def status(self) -> IntegrationStatus:
        return IntegrationStatus.UNSUPPORTED

    def disconnect(self) -> IntegrationStatus:
        return IntegrationStatus.UNSUPPORTED
