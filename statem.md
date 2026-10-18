# State Auto-Save

## Last Updated: 2026-10-18 (MATCH: Этап 3 выполнен — Dialogue Engine + промежуточный LLM-слой)

### Current Task: MATCH — Фаза B. Этап 3 завершён; следующий шаг — Этап 4 (Trust и Compatibility).

- **Проект**: D:\MATCH (Tauri + React + TS клиент, Python + FastAPI сервисы).
- **Git**: HEAD = **c0ab3b1** (локально). services/api (Этапы 1–2) ещё не закоммичены.
- **GitHub**: https://github.com/VladChristmas/match (публичный).
- **CI**: каркас .github/workflows/ci.yml (проверка структуры, зелёный).

### Что сделано
1. **Аудит (Фаза A)**: проект greenfield, окружение проверено, интеграционные
   ограничения площадок изучены. Документы: docs/architecture/audit-report.md.
2. **Окружение установлено**: gh 2.102.0, uv, pnpm, Rust 1.99.1 (msvc).
   MSVC BuildTools 2022 уже был (cl.exe 14.43, SDK 10.0.22621), но не зарегистрирован
   в vswhere → сборка через `. .\scripts\dev-env.ps1`.
3. **Ollama** запущен: модели qwen3.5:9b, qwen3.5-agent, qwen-agent-8k, qwen3.5-9b-optimized (vision/tools).
4. **Скелет репозитория**: apps/ services/ packages/ modules/ adapters/ database/
   tests/ infra/ scripts/ .github/ + README, .gitignore, LICENSE.
5. **Документы Фазы A** (8 шт.) в docs/: audit-report, target-architecture,
   architecture-decisions, data-model, api-proposal, security-review, roadmap, open-questions.
6. **Владелец подтвердил решения**: клиент Tauri; сервер FastAPI; cloud free LLM + Ollama;
   vision-агент (видит экран, не парсит сайт); психопрофиль только пользователю;
   агент пишет в стиле пользователя; без персональных данных, доступ по токенам.
7. **Закрыты OQ-1 и OQ-5**: vision-слой → `Windows.Graphics.Capture` (ADR-0008);
   автономия на старте → авто-отправка (ADR-0009). Документы обновлены
   (open-questions.md, architecture-decisions.md).

### Известные ограничения
- gh CLI отдельно не авторизован; токен берётся из Git Credential Manager (gho_, VladChristmas).
- VS BuildTools не зарегистрирован в vswhere (полная регистрация требует admin).
- `uv` не найден в PATH (вопреки заметке Этапа 0); venv создан через `python -m venv`.
- Порт 5432 занят проектом gl_jb → PostgreSQL Match работает на **5433**
  (`docker compose -f infra/docker-compose.yml up -d db`).
- Реальная деловая логика (модули) ещё не написана — есть только health/config/DB-слой.

### Этап 1 — сделано
- `services/api/`: FastAPI-приложение (`app/main.py`), конфиг через `pydantic-settings`
  (`MATCH_*`), async SQLAlchemy 2.0 (`app/db.py`), модель `users` (`app/models.py`).
- Эндпоинты: `/` (идентификация), `/health` (liveness), `/health/ready` (проверка БД).
- Alembic (async env) + миграция `0001_initial` (таблица `users`).
- Инфра: `services/api/Dockerfile`, `infra/docker-compose.yml` (db + api).
- Тесты (pytest + httpx ASGITransport, sqlite) — 3 passed; ruff — clean.
- CI: добавлен job `backend` (ruff + pytest).
- Проверено вручную: `alembic upgrade head` на PostgreSQL 16 → таблицы `users`,
  `alembic_version`; `/health/ready` → `database: ok`.

### Этап 2 — сделано
- Модели `UserProfile`, `CommunicationProfile`, `UserFeedback` (`app/models.py`).
- Миграция Alembic `0002_profiles_feedback` (upgrade/downgrade проверены на PostgreSQL 16).
- Pydantic-схемы (`app/schemas.py`); временная токен-авторизация (`app/api/deps.py`, ADR-0010):
  `Authorization: Bearer` или `X-Match-Token`, автопровижининг пользователя по `token_ref`.
- API: `GET|PATCH /api/v1/profile`, `GET|PATCH /api/v1/profile/communication`,
  `POST|GET /api/v1/feedback`.
- Тесты 13 passed (sqlite + StaticPool), ruff clean. Живая БД (5433): таблицы созданы.

### Этап 3 — сделано
- Модели `Conversation`, `Message`; миграция `0003_conversations_messages` (up/downgrade ok).
- Промежуточный LLM-слой (`app/llm/`, ADR-0011): `LLMProvider`, `EchoProvider` (default),
  `OllamaProvider`, `LLMGateway`, выбор через `MATCH_LLM_PROVIDER`.
- Dialogue Engine (`app/dialogue/`): style/context/generator/validator/service — генерация и
  валидация ответа в стиле пользователя (границы длины, защита от утечки системного промпта).
- API `app/api/v1/conversations.py`: создания/список/чтение разговоров, импорт сообщений,
  генерация черновиков (`/drafts` только возвращает черновик, не отправляет).
- Тесты 27 passed, ruff clean. Живой smoke на PG 5433: conversation→import→draft (echo) — ok.

### Next Action
1. **Этап 4**: Trust и Compatibility — раздельные оценки риска/взаимности/совместимости.
2. **Этап 6**: полноценный LLM Gateway (облачные free LLM, маршрутизация, fallback, лимиты; OQ-2).
3. Открытые вопросы: OQ-2 (провайдеры; промежуточно ADR-0011), OQ-3 (метрики суперадмина),
   OQ-4 (регистрация VS BuildTools), OQ-6 (локальный SQLite), OQ-7 (токены; промежуточно ADR-0010).
4. Коммиты не делать (запрос владельца); изменения Этапов 1–3 лежат в рабочем дереве.
