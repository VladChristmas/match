# adapters/

Интеграционные адаптеры (единый внутренний интерфейс).

- `manual-import/` — разрешённый режим: пользователь вставляет/импортирует текст диалога.
- `platform-adapters/` — адаптеры площадок; добавляются только при подтверждённых разрешённых способах интеграции.

Нереализуемые/запрещённые возможности возвращают `unsupported` / `not_authorized`, а не имитируют успех.

> Реализация контракта адаптеров (Этап 7): `services/api/app/integrations/`
> (`IntegrationAdapter`, `ManualImportAdapter`, `UnsupportedAdapter`, реестр площадок).
> Contract-тесты — `services/api/tests/test_integrations.py`. Решение — ADR-0014.
