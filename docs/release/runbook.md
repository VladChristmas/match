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

## 8. Сборка установщика и обновление
Релизная сборка (долгая, MSVC-окружение обязательно — через `dev-env.ps1`):
```powershell
. .\scripts\dev-env.ps1
cd apps\desktop
pnpm tauri build
```
Артефакты: `apps\desktop\src-tauri\target\release\bundle\nsis\MATCH_0.1.0_x64-setup.exe`
и `...\msi\MATCH_0.1.0_x64_en-US.msi` (identifier `com.match.desktop`, версия из `tauri.conf.json`).

Обновление:
1. Остановить приложение (и воркер `services/agent-runtime`).
2. Сервер: `alembic upgrade head` до запуска новой версии.
3. Запустить установщик поверх предыдущей версии. Локальная база `match.db`
   в каталоге данных приложения сохраняется (схема версионируется, текущая — v4);
   настройки (адрес API, токен) и оффлайн-очередь сохраняются.
4. После обновления проверить `GET /health/ready` и первый запуск клиента.

Удаление приложения: штатное удаление через Windows; локальная `match.db`
удаляется вместе с каталогом данных приложения (удаление серверных данных —
отдельно, `/api/v1/privacy/deletion-request` или экран «Приватность»).

Предпосылки для машины, где ставится клиент:
- WebView2 Runtime (Evergreen) — предустановлен на Windows 11 и актуальных
  Windows 10; на чистых/урезанных образах ставить отдельно (Edge WebView2).
- Microsoft Visual C++ x64 Redistributable (2015–2022) — рантайм Tauri/WebView2.
- Порт API: клиент обращается к `http://127.0.0.1:8000` по умолчанию
  (`apps/desktop/src/lib/settings.ts`); при ином адресе сервера — задать в
  «Настройки» клиента.
- Бэкенд ставится/обновляется отдельно: compose-стек (`infra/docker-compose.yml`,
  db+api, `alembic upgrade head` на старте контейнера) либо ручной путь runbook §2.

## 9. Проверки перед выкладкой
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

## 10. Эксплуатация
- Пауза авто-отправки: `POST /api/v1/agent/pause`; возобновление — `/resume`.
- Очередь на подтверждение: `GET /api/v1/agent/actions?status=pending`; `approve`/`reject`.
- Отложенная доставка: `POST /api/v1/agent/actions` с `schedule_in_seconds`; статус `scheduled` обрабатывает воркер.
- Экспорт/удаление данных пользователя: `/api/v1/privacy/export`, `/deletion-request`.
- Инциденты и откат: см. `docs/release/rollback-plan.md`.

## 12. Лаборатория тестирования «Эмулятор и тесты»
Вкладка клиента «Эмулятор и тесты» рендерит виртуальный смартфон и прогоняет
8 обязательных сценариев через РЕАЛЬНЫЕ endpoint'ы (vision-наблюдения с
`analyze=true`, decisions, actions, autonomy budget) — имитации агента нет.
ТЗ: `docs/testing/emulator-lab-spec.md`.

GUI: клиент → вкладка «Эмулятор и тесты» → выбрать сценарий → «Запустить
сценарий»; результаты шагов (ожидание/факт/HTTP/время/итог) — в таблице,
live-состояние агента — в панелях справа.

Живой прогон без GUI (регламент/CI), против работающего API:
```powershell
$env:MATCH_BASE_URL="http://127.0.0.1:8000"; $env:MATCH_TOKEN="<токен>"
services\api\.venv\Scripts\python.exe scripts\emulator_lab_live.py
```
Ожидаемый итог: `checks: 31, failed: 0`. При недоступном vision-провайдере
наблюдения честно остаются `analysis_pending=true` (корректное поведение).
Для dev-прогона удобно `MATCH_AUTH_ALLOW_LEGACY_TOKENS=true` и
`MATCH_LLM_PROVIDER=echo` (см. §4).


## 11. Резервная копия и восстановление PostgreSQL

Скрипты (запускать из корня репозитория, имя контейнера — из
`docker compose -f infra/docker-compose.yml ps`):

```powershell
# резервная копия (формата custom, сжатый) → D:\Backup\match-pg-<timestamp>.dump
.\scripts\backup_pg.ps1

# проверка восстановления: дамп восстанавливается в match_restore_check,
# сверяются число таблиц и версия alembic, проверочная БД удаляется
.\scripts\restore_pg.ps1 -BackupFile D:\Backup\match-pg-<timestamp>.dump
```

Полное восстановление боевой базы из дампа (осторожно, перезаписывает):

```powershell
docker exec infra-db-1 sh -c "dropdb -U match match"
docker exec infra-db-1 sh -c "createdb -U match match"
docker cp D:\Backup\match-pg-<timestamp>.dump infra-db-1:/tmp/restore.dump
docker exec infra-db-1 sh -c "pg_restore -U match -d match --no-owner /tmp/restore.dump"
docker exec infra-db-1 rm /tmp/restore.dump
alembic upgrade head   # привести схему к актуальной после восстановления
```

Проверено в этом окружении: дамп → восстановление даёт те же 21 таблиц и
версию миграции `0015` (прогон 2026-10-25).

