# Инструкция по запуску и сопровождению (Этап 9)

## Требования
- Windows, PowerShell 5.1+
- Docker Desktop (PostgreSQL)
- Python 3.11+, Node 22 + pnpm, Rust (MSVC через `scripts/dev-env.ps1`)

## 1. База данных
```powershell
docker compose -f infra/docker-compose.yml up -d db   # PostgreSQL на порту 5433
```

## 2. Сервер (services/api)
```powershell
cd services\api
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
$env:MATCH_DATABASE_URL="postgresql+asyncpg://match:match@localhost:5433/match"
alembic upgrade head
uvicorn app.main:app --reload
```
Проверка: `GET /health` → `status: ok`; `GET /health/ready` → `database: ok`.

## 3. Клиент (apps/desktop)
```powershell
. .\scripts\dev-env.ps1
cd apps\desktop
pnpm install
pnpm tauri dev
```
В приложении: «Настройки» → адрес API и токен → «Проверить соединение».

## 4. Конфигурация (сервер)
Скопировать `services/api/.env.example` в `.env`. Ключевые переменные:
- `MATCH_DATABASE_URL`, `MATCH_LLM_PROVIDER`, `MATCH_LLM_FALLBACK_PROVIDERS`
- `MATCH_LLM_USER_REQUEST_LIMIT`, `MATCH_RATE_LIMIT_PER_MINUTE`
- `MATCH_AUTH_ALLOW_LEGACY_TOKENS` (разрешает использование_legacy_token для разработки)
- `MATCH_CORS_ORIGINS` (список разрешённых origins для фронтенда, пусто = none в production, "*" в development)
- `MATCH_LOG_LEVEL` (DEBUG, INFO, WARNING, ERROR)

## 5. Воркер автономности (services/agent-runtime)
Отдельный процесс для доставки отложенных действий (`scheduled`) и повторных попыток (ADR-0027):
```powershell
services\api\.venv\Scripts\python.exe services\agent-runtime\main.py
```
Настройки: `MATCH_AGENT_WORKER_INTERVAL_SECONDS`, `MATCH_AGENT_MAX_ATTEMPTS`,
`MATCH_AGENT_RETRY_BACKOFF_SECONDS`. Перед запуском — `alembic upgrade head`.

## 6. Наблюдаемость и CORS (этап 27, ADR-0033)
- `MATCH_LOG_LEVEL` (DEBUG/INFO/WARNING/ERROR) — единый формат логов с временем.
- Каждый ответ несёт заголовок `x-request-id` (переданный клиентом или сгенерированный UUID);
  тот же id попадает в лог-строку запроса — использовать при разборе инцидентов.
- Необработанная ошибка → `500` с телом `{"detail": "Internal server error"}`; детали и стек —
  только в логе, не в ответе.
- `MATCH_CORS_ORIGINS` — список origins через запятую. Пусто: в development — `*` (Tauri-dev
  работает с динамическим origin), в production — cross-origin запрещён. Явный список
  работает в обеих средах.

## 7. Расширенные настройки (опционально)
- `MATCH_ADMIN_TOKEN_REFS` (админ-кабинет, OQ-3)
- `MATCH_AGENT_WORKER_INTERVAL_SECONDS`, `MATCH_AGENT_MAX_ATTEMPTS`,
  `MATCH_AGENT_RETRY_BACKOFF_SECONDS`
- `MATCH_VISION_MIN_INTERVAL_SECONDS` (частота LLM-обработки кадров)
- `MATCH_LLM_TIMEOUT_SECONDS`, `MATCH_LLM_MAX_TOKENS`, `MATCH_LLM_TEMPERATURE`
- `MATCH_RATE_LIMIT_BACKEND` ("memory" или "db", см. ADR-0028)

## 8. Проверки перед выкладкой
```powershell
# backend
cd services\api; .\.venv\Scripts\python.exe -m ruff check .; .\.venv\Scripts\python.exe -m pytest -q
# client
cd apps\desktop; pnpm build
```

Нагрузочная проверка (запускать против работающего API, ADR-0028):
```powershell
services\api\.venv\Scripts\python.exe scripts\loadtest.py --base-url http://localhost:8000 `
    --requests 500 --concurrency 20
```

## 9. Эксплуатация
- Пауза авто-отправки: `POST /api/v1/agent/pause`; возобновление — `/resume`.
- Очередь на подтверждение: `GET /api/v1/agent/actions?status=pending`; `approve`/`reject`.
- Отложенная доставка: `POST /api/v1/agent/actions` с `schedule_in_seconds`; статус `scheduled` обрабатывает воркер.
- Экспорт/удаление данных пользователя: `/api/v1/privacy/export`, `/deletion-request`.
- Инциденты и откат: см. `docs/release/rollback-plan.md`.

