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

## 5. Проверки перед выкладкой
```powershell
# backend
cd services\api; .\.venv\Scripts\python.exe -m ruff check .; .\.venv\Scripts\python.exe -m pytest -q
# client
cd apps\desktop; pnpm build
```

## 6. Эксплуатация
- Пауза авто-отправки: `POST /api/v1/agent/pause`; возобновление — `/resume`.
- Очередь на подтверждение: `GET /api/v1/agent/actions?status=pending`; `approve`/`reject`.
- Экспорт/удаление данных пользователя: `/api/v1/privacy/export`, `/deletion-request`.
- Инциденты и откат: см. `docs/release/rollback-plan.md`.
