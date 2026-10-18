# State Auto-Save

## Last Updated: 2026-10-18 (MATCH: Этапы 0–14 выполнены; миграции 0001–0010)

### Current Task: MATCH — Этапы 0–14 пройдены (предрелиз + vision + токены + CI + лимитер на БД). Дальше — админ-метрики и локальное хранилище.

- **Проект**: D:\MATCH (Tauri + React + TS клиент, Python + FastAPI сервисы).
- **Git**: HEAD = **f66efa6** (этап 13, запушено). Этап 14 — локальный коммит.
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

### Этап 4 — сделано
- Модели `CompatibilityAssessment`, `RiskAssessment`; миграция `0004_assessments` (up/downgrade ok).
- Движки: `app/trust/engine.py` (сигналы риска, severity, рекомендованное действие),
  `app/compatibility/engine.py` (Jaccard целей/ценностей, lifestyle, взаимность, uncertainty).
- API `app/api/v1/analysis.py`: `POST|GET /api/v1/analysis/compatibility`, `POST|GET /api/v1/analysis/risk`.
- Тесты 38 passed, ruff clean. Живой smoke PG 5433: 9 таблиц.

### Этап 6 — сделано (LLM Gateway)
- `OpenAICompatProvider` (облачный OpenAI-совместимый API) + `OllamaProvider` + `EchoProvider`.
- `LLMGateway`: порядок провайдеров, fallback, `LLMUnavailable` → 503; `ModelRun` + миграция `0005_model_runs`;
  per-user лимит запросов → 429. Тесты 47 passed.

### Этап 5 — сделано (apps/desktop)
- Tauri 2 + React 19 + TS + Vite. Оболочка Rust: команды `load_settings`/`save_settings`
  (config-dir) и `app_info` (`src-tauri/src/lib.rs`).
- UI-разделы: Профиль (цели/ценности/границы + профиль общения), Знакомства (разговоры,
  импорт сообщений, генерация черновиков), Анализ (совместимость/риск + история),
  Автономность (режимы), Журнал (обратная связь + локальный лог), Настройки (API/токен).
- Типизированный REST-клиент (`src/lib/api.ts`) под существующие endpoint'ы; Bearer-токен (ADR-0010).
- Проверено: `pnpm build` (tsc + vite) ok; `cargo check` (MSVC через `scripts/dev-env.ps1`) ok.
- CI: jobs `desktop-web` (ubuntu) и `desktop-rust` (windows-latest).
- Ограничение: vision-слой (Windows.Graphics.Capture, ADR-0008) ещё не подключён.

### Этап 7 — сделано (services/api)
- Контракт адаптера `IntegrationAdapter` (`app/integrations/base.py`): `platform_id`,
  `display_name`, `capabilities`, `status()`, `disconnect()`; `IntegrationStatus` (StrEnum).
- `ManualImportAdapter` (поддержан) + `UnsupportedAdapter` (Tinder, Badoo, Bumble, OkCupid,
  Hinge, Мамба); реестр площадок (`registry.py`, lru_cache-синглтон).
- API `app/api/v1/integrations.py`: `GET /api/v1/integrations`, `/{platform_id}/capabilities`,
  `/{platform_id}/status`, `POST /{platform_id}/disconnect` (для `unsupported` → 409).
- Contract-тесты `tests/test_integrations.py` (тип-контракт через runtime_checkable Protocol).
- Тесты 63 passed (было 47), ruff clean. ADR-0014; обновлены api-proposal и adapters/README.

### Этап 8 — сделано (services/api + apps/desktop)
- Модели `AgentSettings`, `AgentAction`; миграция `0006_agent_autonomy` (up/down проверены на PG 5433).
- `app/agent/service.py`: очередь (`pending`/`sent`/`rejected`), идемпотентность по `Idempotency-Key`,
  автодоставка в `auto_send`, передача человеку (`approve`/`reject`), общая пауза.
- API `app/api/v1/agent.py`: `GET|PATCH /agent/settings`, `POST /agent/pause|resume`,
  `GET|POST /agent/actions`, `POST /agent/actions/{id}/approve|reject`.
- Клиент: `AutonomyView` подключён к API (состояние, пауза/возобновление, очередь approve/reject).
- Тесты 73 passed (было 63), ruff clean. Живой PG 5433: 12 таблиц. ADR-0015.

### Этап 9 — сделано (services/api + docs/release)
- Приватность: `app/api/v1/privacy.py` — `GET /privacy/export` (полный экспорт, `token_ref` редактируется),
  `POST /privacy/deletion-request` (явное удаление всех данных пользователя, не полагается на FK-каскад).
- Нагрузка: `app/api/ratelimit.py` (in-process скользящее окно), `MATCH_RATE_LIMIT_PER_MINUTE`
  (0 = выкл), применено к `/drafts` и `/agent/actions` → `429`.
- Документы: `docs/release/pre-release-checklist.md`, `rollback-plan.md`, `runbook.md`; ADR-0016.
- Тесты 79 passed (было 73), ruff clean.

### Этап 10 — сделано (services/api + apps/desktop + docs)
- Сервер: модель `VisionObservation`; миграция `0007_vision_observations` (up/down проверены на PG 5433).
  `app/vision/service.py` — проверка PNG (магия, размеры, лимит 8 МБ, SHA-256), изображение НЕ хранится.
  API `app/api/v1/vision.py`: `GET|POST /api/v1/vision/observations` (rate-limited, проверка владельца).
  Приватность: наблюдения включены в `/privacy/export` и `/privacy/deletion-request`.
- Клиент (Rust): `src-tauri/src/vision.rs` — `Windows.Graphics.Capture` (крейт `windows` 0.62):
  `list_capture_windows`, `capture_window_frame` (D3D11 staging → BGRA→RGBA, box-downscale до 1280 px → PNG base64).
- Клиент (UI): `VisionView` (вкладка «Зрение») — список окон, снятие кадра, предпросмотр, отправка, история.
- Тесты 85 passed (было 79), ruff clean; `cargo clippy -D warnings` и `cargo fmt --check` чисто; `pnpm build` ok.
- Документы: ADR-0017; api-proposal (раздел «Зрение»); OQ-8 (мультимодальная модель); README/roadmap обновлены.

### Этап 11 — сделано (services/api + apps/desktop + docs)
- Анализ кадров: `app/vision/base.py` (`VisionProvider`), `app/vision/providers.py`
  (`OllamaVisionProvider` — локальный по умолчанию; `OpenAICompatVisionProvider` — облако, только по ключу),
  `app/vision/gateway.py` (`VisionGateway` + fallback, `VisionUnavailable`).
- Миграция `0008_vision_analysis` — колонки `provider`, `model` у `vision_observations` (up/down на PG 5433).
- API: `POST /api/v1/vision/observations` выполняет анализ при приёме (`analyze=true` по умолчанию),
  пишет `summary`/`provider`/`model`, `analysis_pending=False`, и `ModelRun` (task_type=vision_observation)
  с общим per-user лимитом; при недоступной модели наблюдение сохраняется с `analysis_pending=True`.
- Клиент: вкладка «Зрение» — тумблер анализа, показ summary/провайдера в истории.
- Тесты 89 passed (было 85), ruff clean; `pnpm build` ok. ADR-0018.

### Этап 12 — сделано (services/api + apps/desktop + docs)
- Токены доступа (закрытие OQ-7): `app/auth/service.py` — генерация (`match_` + `secrets.token_urlsafe(32)`),
  хранение только SHA-256, `resolve_access_token`/`is_known_token`/`create_token`/`list_tokens`/
  `revoke_token`/`rotate_token`.
- Модель `AccessToken` + миграция `0009_access_tokens` (up/down на PG 5433).
- API `app/api/v1/tokens.py`: `GET /api/v1/tokens`, `POST /api/v1/tokens`, `POST /{id}/rotate`, `DELETE /{id}`
  (только владелец; отозванный → 409 при ротации, 404 для чужого).
- Авторизация: `get_current_user` сначала проверяет выданные токены, затем легаси `token_ref`
  (ADR-0010), который отключается `MATCH_AUTH_ALLOW_LEGACY_TOKENS=false`; отозванные/известные токены
  в легаси-путь не попадают.
- Приватность: метаданные токенов в экспорте (без хэша), удаляются при удалении аккаунта.
- Клиент: раздел «Токены доступа» в настройках — выдача (с показом токена один раз), список,
  ротация, отзыв, «Использовать этот токен».
- Тесты `tests/test_tokens.py` (7 шт.), всего 96 passed; ruff clean; `pnpm build` ok. ADR-0019.

### Этап 13 — сделано (CI + scripts + docs)
- CI (`.github/workflows/ci.yml`): backend — добавлен `ruff format --check`; desktop-rust — вместо `cargo check`
  теперь `cargo fmt --check` и `cargo clippy --all-targets -- -D warnings`.
- Ruff-формат приведён к единому виду: `ruff format .` (33 файла переформатировано, 47 без изменений),
  конфиг общий (`line-length=100`), тесты после переформатирования — 96 passed.
- Локальный скрипт `scripts/check.ps1` — единый прогон (ruff format/check, pytest, pnpm build, cargo fmt/clippy);
  файл сохранён в UTF-8 с BOM (PS 5.1 иначе ломает кириллицу). Проверен локально: все шаги зелёные.
- README: раздел «Проверки перед коммитом», исправлен запуск `dev-env.ps1` (dot-source).

### Этап 14 — сделано (services/api + docs)
- Лимитер нагрузки получил бэкенды (`MATCH_RATE_LIMIT_BACKEND`): `memory` (по умолчанию, скользящее
  окно in-process) и `db` — фиксированные окна 60 с в таблице `rate_limit_counters` (работает
  при нескольких инстансах, без Redis).
- Модель `RateLimitCounter` + миграция `0010_rate_limit_counters` (up/down на PG 5433; 15 таблиц).
- `app/api/ratelimit.py`: `_memory_hits/_memory_add`, `_db_hits` (с удалением устаревших окон),
  `_db_increment` (SAVEPOINT + IntegrityError → UPDATE, без диалект-специфичного ON CONFLICT),
  `enforce_rate_limit(session, key)`; отклонённые запросы счётчик не увеличивают.
- `rate_limit_dependency` теперь принимает сессию; удаление аккаунта чистит счётчики
  (в экспорт приватности служебные счётчики не входят).
- Тесты `tests/test_ratelimit.py` (+2: лимит и изоляция пользователей на db-бэкенде), всего 98 passed;
  ruff format/check clean. ADR-0020.

### Git (локально)
- Коммиты: … d7be68b (stage11), abcbeb0+761d62e (stage12), e4dfada+f66efa6 (stage13). Запушено до f66efa6.

### Next Action
1. Этап 15: кабинет суперадмина (OQ-3) — роль admin + метрики.
2. Этап 14: лимитер на БД (multi-instance). Этап 15: кабинет суперадмина (OQ-3). Этап 16: локальное хранилище клиента (OQ-6).
3. OQ-8: выбрать конкретную мультимодальную модель (`MATCH_VISION_MODEL`). Открытые: OQ-2..OQ-4, OQ-6, OQ-8.
