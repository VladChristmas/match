# Match

Персональный AI-агент для знакомств (гибридный: Windows-клиент + локальная обработка + облачные LLM).

> Статус: **Этапы 1–9 выполнены (предрелиз)**. Реализация шла поэтапно, см. [`docs/implementation-plan/roadmap.md`](docs/implementation-plan/roadmap.md).

## Принципы

- Агент **видит экран** (vision), не парсит и не подключается к площадкам напрямую.
- Психологический портрет собеседника виден **только пользователю**; агент общается в стиле пользователя.
- Строго прописанные сценарии LLM; входящие сообщения — недоверенный ввод (защита от prompt injection).
- Персональные данные не собираются; доступ по токенам.
- Локальный fallback — Ollama (`qwen3.5:9b`), основной режим — облачные free LLM.

## Стек

| Слой | Технология |
|---|---|
| Клиент | Tauri + React + TypeScript |
| Серверные сервисы | Python + FastAPI |
| БД | PostgreSQL (Docker) + локальное хранилище |
| Модели | LLM Gateway (cloud free + Ollama) |

## Документы Фазы A

- [Аудит](docs/architecture/audit-report.md)
- [Целевая архитектура](docs/architecture/target-architecture.md)
- [Архитектурные решения](docs/architecture/architecture-decisions.md)
- [Модель данных](docs/architecture/data-model.md)
- [API](docs/api/api-proposal.md)
- [Безопасность](docs/security/security-review.md)
- [Roadmap](docs/implementation-plan/roadmap.md)
- [Открытые вопросы](docs/implementation-plan/open-questions.md)
- [Чек-лист предрелиза](docs/release/pre-release-checklist.md)
- [План отката](docs/release/rollback-plan.md)
- [Инструкция (runbook)](docs/release/runbook.md)

## Разработка

Среда сборки Rust/Tauri требует загрузки MSVC-окружения (VS BuildTools 2022 не зарегистрирован в `vswhere`):

```powershell
.\scripts\dev-env.ps1   # импортирует vcvars64 в текущую сессию
```

Клиент (`apps/desktop`, Tauri + React + TS):

```powershell
. .\scripts\dev-env.ps1
cd apps\desktop
pnpm install
pnpm tauri dev
```

Сервер (`services/api`, FastAPI):

```powershell
docker compose -f infra/docker-compose.yml up -d db   # PostgreSQL на порту 5433
cd services\api
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload
```

## Лицензия

MIT — см. [LICENSE](LICENSE).
