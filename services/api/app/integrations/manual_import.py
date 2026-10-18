from app.integrations.base import IntegrationCapabilities, IntegrationStatus


class ManualImportAdapter:
    """Разрешённая интеграция: пользователь копирует/вставляет текст сообщений.

    Реальное подключение к площадке отсутствует, поэтому `disconnect` — это
    осознанный no-op, переводящий адаптер в состояние `disconnected`.
    """

    platform_id = "manual_import"
    display_name = "Ручной импорт"

    capabilities = IntegrationCapabilities(
        supported=True,
        manual_import=True,
        requires_authorization=False,
    )

    def __init__(self) -> None:
        self._connected = True

    def status(self) -> IntegrationStatus:
        if self._connected:
            return IntegrationStatus.AVAILABLE
        return IntegrationStatus.DISCONNECTED

    def disconnect(self) -> IntegrationStatus:
        self._connected = False
        return self.status()
