# State Auto-Save

## Last Updated: 2026-10-18 (MATCH: Этапы 0–16 выполнены; миграции 0001–0011)

### Current Task: MATCH — Этапы 0–16 пройдены: план реализации выполнен полностью. Дальше — OQ-2/OQ-4/OQ-8 (выбор провайдеров/моделей и MSVC).

- **Проект**: D:\MATCH (Tauri + React + TS клиент, Python + FastAPI сервисы).
- **Git**: HEAD = **b5d1dcf** (этап 15, запушено). Этап 16 — локальный коммит.
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

### Этап 15 — сделано (services/api + apps/desktop + docs)
- Роль `admin`: колонка `users.role` + миграция `0011_user_role` (up/down на PG 5433); повышение по
  списку `MATCH_ADMIN_TOKEN_REFS` (`maybe_promote_admin`) при первом запросе.
- API `app/api/v1/admin.py`: `GET /api/v1/admin/metrics` и `GET /api/v1/admin/whoami` под `AdminUser`
  (403 без роли). Метрики (`app/admin/service.py`): пользователи по ролям, диалоги по статусу,
  сообщения по обработке, запуски моделей по задаче и провайдеру, наблюдения vision по провайдеру,
  действия агента по статусу, отзывы по типу, токены active/revoked + сводка несекретных настроек.
  Персональные данные и тексты в метрики не попадают (тест это проверяет).
- Клиент: вкладка «Админ» (`AdminView.tsx`) — сводка, таблицы метрик, понятное объяснение 403.
- Тесты `tests/test_admin.py` (6 шт.), всего 104 passed; ruff format/check clean; `pnpm build` ok. ADR-0021; OQ-3 закрыт.

### Этап 16 — сделано (apps/desktop + CI + docs)
- Локальное хранилище клиента на SQLite (закрытие OQ-6): `src-tauri/src/storage.rs` — `match.db` в
  каталоге данных приложения, `rusqlite` (bundled). Таблицы `settings(key,value)` и
  `journal(id,at,kind,summary,detail)` + индекс по времени; версия схемы в `PRAGMA user_version`.
- Команды: `load_state`, `save_state` (настройки без блоба журнала), `journal_append` (идемпотентно
  по id, подрезка до 500), `journal_clear`, `storage_info`. Легаси `settings.json` переносится
  однократно и переименовывается в `settings.json.migrated`. Старые команды `load_settings`/
  `save_settings` удалены (их заменил storage).
- Клиент: `src/lib/storage.ts`, `AppContext` пишет журнал в SQLite, раздел «Локальное хранилище»
  в настройках (путь, версия SQLite/схемы, записей журнала, размер). В браузере — localStorage.
- Rust-тесты хранилища (4 шт.): миграция идемпотентна, настройки сохраняются без журнала,
  журнал сортирован и подрезан до лимита, повторная запись не дублируется. `cargo test` добавлен
  в CI и в `scripts/check.ps1`.
- Всего: 104 pytest + 4 cargo test passed; ruff format/check clean; `pnpm build` ok. ADR-0022; OQ-6 закрыт.

### Этап 17 — сделано (services/api + docs)
- Закрытие OQ-8: по умолчанию локальная мультимодальная модель `MATCH_VISION_MODEL=qwen3.5:9b`
  (Ollama; capability `vision` подтверждена `ollama show`), поэтому кадр по умолчанию не покидает
  машину; облачный `OpenAICompatVisionProvider` остаётся opt-in по ключу.
- Троттлинг частоты анализа: `MATCH_VISION_MIN_INTERVAL_SECONDS` (по умолчанию `0` = выкл).
  `app/vision/service.py: is_analysis_throttled`; в `POST /vision/observations` при превышении
  частоты кадр всё равно записывается (`analysis_pending=true`), вызов модели пропускается.
- Тест `test_analysis_throttled_by_min_interval`; docstring vision-сервиса актуализирован. ADR-0023; OQ-8 закрыт.

### Этап 18 — сделано (services/api + docs)
- Закрытие OQ-2: `MATCH_LLM_PRESET` (`groq`/`gemini`/`openrouter`/`cerebras`) подставляет
  `base_url` и модель OpenAI-совместимого облака — пользователю достаточно задать ключ
  `MATCH_OPENAI_API_KEY` (`app/llm/presets.py`). Пресет приоритетнее явных `MATCH_OPENAI_*`;
  без пресета поддержан любой OpenAI-совместимый endpoint.
- Рекомендуемый порядок `openai,ollama,echo`; без ключа облачный слот пропускается (дефолт
  остаётся приватным/оффлайновым). Политика лимитов — `MATCH_LLM_USER_REQUEST_LIMIT` +
  `MATCH_LLM_TIMEOUT_SECONDS`; описана в `docs/release/free-llm-providers.md`.
- Тесты `tests/test_llm_presets.py` (5 шт.). ADR-0024; OQ-2 закрыт.

### Этап 19 — сделано (scripts + docs)
- Закрытие OQ-4: основным остаётся dot-source `scripts/dev-env.ps1` (полная регистрация
  BuildTools в vswhere требует прав администратора и не нужна). `dev-env.ps1` получил
  автопоиск `vcvars64.bat` (x86/x64 Program Files) вместо одного жёсткого пути.
- Добавлен диагностический `scripts/msvc-status.ps1`: vswhere, vcvars, toolset (14.43),
  Windows SDK (10.0.22621), рекомендация; не требует прав администратора.
- Проверено: `msvc-status.ps1` отрабатывает, `dev-env.ps1` находит cl.exe и rustc работает.
  Оба скрипта — UTF-8 с BOM. ADR-0025; OQ-4 закрыт; открытых вопросов нет.

### Этап 20 — сделано (apps/desktop + docs)
- Оффлайн-очередь отправки (завершает OQ-6 в части очереди): таблица `outbox` в SQLite-базе
  `match.db`, схема БД поднята до версии 2 (`storage.rs`). Колонки: id, at, method, path, body,
  idempotency_key, label, attempts, last_error. Команды `outbox_add/list/remove/fail/clear`;
  `storage_info` отдаёт `outbox_entries`.
- Клиент: `src/lib/outbox.ts` (`enqueueOutbox`, `listOutbox`, `flushOutbox`), `ApiClient.send`;
  `AppContext` повторяет очередь при событии `online`, по таймеру (30 с) и кнопке; результат
  журналируется. Импорт/отправка сообщения в MatchesView при сетевой ошибке (`status 0`)
  ставится в очередь. Раздел «Локальное хранилище» показывает счётчик и кнопку «Синхронизировать».
- Rust-тесты хранилища (7 шт., +3: outbox roundtrip/remove, fail+attempts, миграция v1→v2).
  Всего 110 pytest + 7 cargo test; ruff/clippy/fmt clean; `pnpm build` ok. ADR-0026.

### Этап 21 — сделано (services/api + services/agent-runtime + docs)
- Отложенная доставка: миграция `0012_agent_schedule` добавляет в `agent_actions` колонки
  `scheduled_at` и `next_attempt_at` (+индекс; up/down проверены на PG 5433).
- API: `POST /api/v1/agent/actions` принимает `schedule_in_seconds`; в режиме `auto_send` и без
  паузы действие получает статус `scheduled` (иначе `pending`). Статусы `scheduled`/`failed`.
- Воркер `app/agent/worker.py`: `deliver_due` (поиск просроченных `scheduled`, доставка,
  retry с линейным backoff, после `MATCH_AGENT_MAX_ATTEMPTS` → `failed`), `run_forever`.
  Отдельный процесс `services/agent-runtime/main.py` (+README) использует код и venv `services/api`.
- Настройки: `MATCH_AGENT_WORKER_INTERVAL_SECONDS`, `MATCH_AGENT_MAX_ATTEMPTS`,
  `MATCH_AGENT_RETRY_BACKOFF_SECONDS` (в `.env.example`).
- Тесты `tests/test_agent_worker.py` (4 шт.), всего 114 pytest; ruff clean. Проверено: воркер
  стартует и подключается к PG. ADR-0027.

### Этап 22 — сделано (services/api + scripts + docs)
- Сквозной тест `tests/test_e2e_flow.py`: профиль → разговор → импорт → черновик → совместимость
  → риск → отзыв → отложенное действие (через воркер) → vision → экспорт приватности → удаление;
  оффлайн, провайдер `echo`, vision-шлюз пустой. Всего 115 pytest.
- Нагрузочная проверка `scripts/loadtest.py` (асинхронный httpx): `--requests/--concurrency/--method/
  --path/--token`, печатает rps и перцентили и распределение статусов. Проверено против uvicorn:
  300 GET /health при 20 параллельных — 300/300, ~126 req/s.
- ruff clean. ADR-0028. Продуктовый план (этапы 17–22) закрыт.

### Git (локально)
- Коммиты: … e4dfada+f66efa6 (stage13), b73e77f+96787a8 (stage14), 94f2056+b5d1dcf (stage15). Запушено до b5d1dcf.

### Next Action
1. Все открытые вопросы закрыты: OQ-2 (ADR-0024, Этап 18), OQ-4 (ADR-0025, Этап 19),
   OQ-8 (ADR-0023, Этап 17); ранее OQ-3/OQ-6/OQ-7.
2. Сделано: Этапы 17–22 (vision OQ-8, free LLM OQ-2, MSVC OQ-4, оффлайн-очередь, воркер
   автономности, e2e/нагрузка). Продуктовый план закрыт. Из «вне релиза» остаются реальные
   интеграции с площадками (по дизайну агент не подключается к площадке).
3. **Этапы 23–24 реализованы (код, тесты, ADR-0029/ADR-0030):** Decision Loop + политика действий,
   журнал `agent_decisions`, стоп-факторы, `/agent/decisions` (`tests/test_decision.py`); Memory Lifecycle
   на клиенте (`memories`/`memory_events` в `match.db`, команды `memory_*`, тесты в `storage.rs`).
   Далее Этап 25 Relationship Dynamics — вопросы OQ-9…OQ-12 (`open-questions.md`) остаются открытыми.
