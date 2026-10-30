# Техническое задание: встроенная лаборатория тестирования «Эмулятор и тесты» (MATCH)

- Статус: ТЗ на реализацию (создано 2026-10-27)
- Цель: дать возможность проверять поведение агента в мобильных сценариях внутри
  Windows-приложения, без покупки отдельного смартфона и без переключения между окнами.
- Жёсткое правило: **симулятор не имитирует успешную работу агента**. Кадры виртуального
  телефона проходят реальную `Vision`-цепочку и реальную цепочку принятия решений через
  существующие HTTP-endpoints бэкенда. Никаких «зелёных» тестов на локальных заглушках.

## 1. Границы (что делаем / чего не делаем)

| Режим | Что проверяет | Этап |
|---|---|---|
| **Симулятор Match** (вкладка «Эмулятор и тесты») | Логику агента, память, решения, автономность, распознавание тестовых экранов; composed-сценарии с ожидаемыми результатами | **Это ТЗ (Фаза 1)** |
| **Реальный Android-эмулятор** (ADB screencap) | Совместимость с конкретными приложениями знакомств, жесты, системные ограничения Android | Фаза 2 — только интерфейс-адаптер закладываем сейчас, реализация позже |

Не входим в объём Фазы 1:
- встраивание Android-эмулятора/QEMU в окно приложения;
- новые backend-endpoints (используем только существующие, см. §4);
- изменения в `app/vision/*`, `app/decision/*`, `app/agent/*`, `app/autonomy/*`, моделях
  и миграциях Alembic — рабочие модули не переписываются;
- хранение изображений где-либо (кадр остаётся метаданными + SHA-256, ADR-0007/0008).

## 2. Точки интеграции в существующем коде (проверено разведкой)

Desktop-клиент (`D:\MATCH\apps\desktop`):
- Вкладки: `src/App.tsx` — тип `Tab` (строки 20–32), массив `TABS` (34–47), рендер в `Shell()`
  (104–117). Добавляется один пункт.
- Сохранение активной вкладки: `src/lib/activeTab.ts` (`loadActiveTab`/`saveActiveTab`,
  строки 53/57 в `App.tsx`). Новый id вкладки должен быть строкой — совместимо.
- Клиентский Vision-сервис: `src/lib/vision.ts` — `captureWindowFrame(handle)` идёт в
  Tauri-команду (`src-tauri/src/lib.rs:27–36`). Для симулятора **не используется**: кадр
  рендерится локально в `<canvas>` (см. §3).
- Отправка кадра: `src/lib/api.ts` — `ApiClient.createVisionObservation`
  (строки 289–294: `POST /api/v1/vision/observations`, тело `VisionObservationCreate`:
  `conversation_id`, `frame_base64`, `source_label`, `captured_at`, `analyze`).
- Операции агента уже есть в `ApiClient`: `listActions` (253), `createAction` (259 — шлёт
  заголовок `Idempotency-Key`), `approveAction` (269), `rejectAction` (275),
  `evaluateDecision` (329), `pauseAgent`/`resumeAgent` (245/249), `getAutonomyBudget`/
  `updateAutonomyBudget` (338/342), `listAutonomyErrors` (349), `listDecisions` (323).
- Типы: `src/lib/types.ts` (строки 215–260 — Vision-типы; агентские типы рядом).
- Таймаут/abort запросов: `API_TIMEOUT_MS = 20000` (api.ts:67) — раннер переиспользует
  оффлайн-outbox/retry-механику `AppContext` (`src/context/AppContext.tsx:123–144`).

Backend (`D:\MATCH\services/api`):
- `POST /api/v1/vision/observations` (`app/api/v1/vision.py:58–125`): декодирует PNG
  (`decode_png_frame` — валидация сигнатуры, лимит `MAX_FRAME_BYTES = 8 МиБ`, размеры из
  IHDR), пишет метаданные, при `analyze=true` вызывает реальный `VisionGateway`
  (Ollama локально / OpenAI opt-in), троттлинг `MATCH_VISION_MIN_INTERVAL_SECONDS`,
  лимит `MATCH_LLM_USER_REQUEST_LIMIT` → 429.
- `POST /api/v1/agent/decisions/evaluate` (`decisions.py:39–54`): реальный `build_state` +
  `decide` без исполнения.
- `POST /api/v1/agent/actions` (`agent.py:110–143`): `Idempotency-Key` header; 201 при
  создании, 200 при повторе с тем же ключом (доказательство отсутствия дубля).
- `POST /api/v1/agent/actions/{id}/approve|reject` (`agent.py:146–173`), `pause`/`resume`
  (75–90), `PATCH /api/v1/autonomy/budget` (`autonomy.py:44`).

## 3. Виртуальный смартфон (Фаза 1A)

Рендер — на `<canvas>` 2D, а не захват окна приложения. Причины: (1) кадр телефона не
должен содержать сам лаб-интерфейс; (2) работает и в dev-браузере (без Tauri); (3) детерминизм.

**Разделение логики для тестируемости** (паттерн как в `src/lib/llmStatus.ts` — pure-логика
+ тонкая обвязка):

- `src/lib/emulator/scene.ts` — **чистые функции** (без DOM):
  - `buildScene(screen: VirtualScreen, opts: {orientation, scale}): DrawCommand[]` —
    список операндов отрисовки (`rect`, `roundRect`, `text`, `image-less` — без внешних
    ассетов; системный шрифт-стек фиксирован: `"system-ui, sans-serif"`).
  - `RESOLUTIONS` — пресеты: `360×640`, `390×844`, `412×915` (портрет); альбом — те же
    с поменянными местами стороны. Ширина кадра ≤ 1280 px (как `MAX_FRAME_WIDTH` в
    `src-tauri/src/vision.rs`).
  - `captureVirtualFrame(canvas, screen, opts): {png_base64, width, height}` — вызывается
    после `paint(ctx, buildScene(...))`; `png_base64` — `data:image/png;base64,...` без
    префикса (формат, который ждёт `decode_png_frame`).
- `src/lib/emulator/screen.ts` — модель данных `VirtualScreen` (сериализуемая):
  ```ts
  type ScreenMode = "matches" | "chat" | "profile" | "notification";
  interface VirtualChat { peerName: string; messages: VirtualMessage[]; typing?: boolean }
  interface VirtualMessage { id: string; inbound: boolean; text: string; at: string }
  interface VirtualProfile { name: string; age: number; city: string; bio: string; interests: string[] }
  interface VirtualScreen {
    mode: ScreenMode;
    statusBar: { clock: string; battery: number };   // детерминированные значения из сценария
    chat?: VirtualChat; profile?: VirtualProfile;
    feed?: { name: string; age: number; city: string }[];
    notification?: { app: string; title: string; body: string };
  }
  ```
- `src/lib/emulator/frameSource.ts` — **интерфейс-адаптер** (Фаза 2):
  ```ts
  interface FrameSource {
    readonly kind: "simulator" | "android-adb";
    capture(screen: VirtualScreen): Promise<{ png_base64: string; width: number; height: number }>;
  }
  export const simulatorFrameSource: FrameSource = { kind: "simulator", capture: ... };
  // androidAdbFrameSource — НЕ реализуется в Фазе 1; только точка расширения.
  ```
  Сценарии (§4) обращаются к `FrameSource`, а не к конкретному источнику — поэтому
  сценарии Фазы 1 переиспользуются на реальном Android без изменений.

## 4. Сценарии и движок прогона (Фаза 1B)

Сценарий — **данные**, а не хардкод. Новые сценарии добавляются без правки движка.

```ts
// src/lib/emulator/scenario.ts
type StepKind =
  | "show_screen"        // отрисовать экран (render + capture НЕ обязательны)
  | "capture_observation" // show_screen → capture → POST /api/v1/vision/observations (analyze: true)
  | "import_message"     // импорт входящего сообщения в диалог (существующий endpoint импорта)
  | "evaluate_decision"  // POST /api/v1/agent/decisions/evaluate { conversation_id, text }
  | "create_action"      // POST /api/v1/agent/actions (Idempotency-Key детерминированный)
  | "wait_outbox_flush"  // дождаться синхронизации офлайн-очереди клиента (из AppContext)
  | "assert_state";      // чтение actions/decisions/budget + проверка ожидания

interface ScenarioStep {
  id: string;                    // уникален в сценарии; входит в Idempotency-Key
  kind: StepKind;
  title: string;                 // человекочитаемое описание шага
  conversation_id: string;       // тестовый диалог из seed-набора сценария
  payload?: Record<string, unknown>;  // VirtualScreen | text | schedule_in_seconds | ...
  expect: Expectation;
}
interface Expectation {
  predicate: "observation_analyzed" | "observation_pending" | "decision_mode_in"
           | "action_status_is" | "no_duplicate_action" | "http_status_is"
           | "budget_field_is";
  args?: Record<string, string | number | boolean | string[]>;
}
interface Scenario { id: string; title: string; steps: ScenarioStep[]; }
```

Движок `src/lib/emulator/runner.ts`:
- Состояния: `idle → running ⇄ paused → done | failed`; кнопки UI: «Запустить сценарий»,
  «Пауза», «Продолжить», «Сбросить». Защита от двойного старта (guard-флаг).
- Шаги выполняются **строго последовательно**; `AbortController` rerun/сброса — переиспользуем
  abort-механику `ApiClient` (`API_TIMEOUT_MS`).
- Идемпотентность: ключ `match-emu-{scenario_id}-{step_id}` — детерминированный, поэтому
  повторный прогон того же сценария доказывает отсутствие дублей (201 → 200, тот же `id`).
- Результат шага:
  ```ts
  interface StepResult {
    step_id: string; title: string;
    ok: boolean;                          // expectation выполнилось
    http_status?: number;                 // фактический код, если был HTTP-вызов
    expected: string; actual: string;     // человекочитаемо (предикат и факт)
    duration_ms: number;                  // замер клиента (roundtrip)
    error?: string;                       // текст ошибки/рейзa
    observation?: { analysis_pending: boolean; summary: string | null; provider: string | null };
    action?: { id: string; status: string };
    duplicate?: boolean;                  // ответ 200 на create_action = повтор по ключу
  }
  ```
- `src/lib/emulator/expectations.ts` — **чистая функция** `checkExpectation(expect, ctx):
  {ok, actual, reason}` — без сети/DOM, покрывается node-тестами (вынести предикаты сюда
  из runner.ts обязательно).
- Порядок шага `capture_observation` строго: `buildScene → paint → captureVirtualFrame →
  api.createVisionObservation({..., analyze: true})`. Параметр `source_label` = `"emulator"`.

Обязательный набор сценариев (данные в `src/lib/emulator/scenarios.ts`):

1. `new_match_first_message` — знакомство → первое сообщение → ожидание: решение не
   `stop`, наблюдение проанализировано.
2. `continue_with_memory` — диалог с историей, ссылка на прошлый контекст в промпте кадра
   (текст в `VirtualChat`), ожидание: `decision_mode_in [execute, verify]`.
3. `ambiguous_message` — неоднозначное входящее → ожидание: `decision_mode_in [escalate, verify]`,
   авто-отправки нет.
4. `boundaries_and_loss_of_interest` — отказ/смена интереса в чате → ожидание: не `execute`.
5. `context_loss_similar_names` — два диалога, похожие имена → ожидание: действие привязано
   к верному `conversation_id` (поле действия в `StepResult.action`).
6. `pause_cancel_restart` — `pause` → `create_action` pending → `reject` → `resume`;
   ожидание: `action_status_is rejected`, сообщений не отправлено.
7. `retry_no_duplicate` — `create_action` дважды с одним `Idempotency-Key` → ожидание
   `no_duplicate_action` (201 затем 200, один `id`).
8. `autonomy_limits` — бюджет: дневной лимит/глобальная пауза → ожидание 409 с причиной
   «global_paused»/«daily_limit_exceeded» (как в `test_agent.py:150–188`).

Каждый сценарий несёт seed-данные: 2–3 тестовых диалога (`conversation_id`) + начальные
сообщения — создаём через существующие endpoints (создание диалога / импорт), не прямыми
вставками в БД.

## 5. UI вкладки (Фаза 1C) — `src/views/EmulatorView.tsx`

Раскладка в три колонки:
1. **Виртуальный смартфон** — `<canvas>` в рамке телефона; тумблеры портрет/альбом,
   селект разрешения, слайдер масштаба. Под рамкой — быстрый выбор тестового экрана
   («Лента знакомств», «Переписка», «Профиль», «Уведомление»).
2. **Управление тестом** — кнопки «Запустить сценарий», «Пауза», «Продолжить», «Сбросить»,
   выбор сценария из выпадающего списка. Ниже — live-панель: действия агента
   (`api.listActions`), решения (`api.listDecisions` / результат `evaluate_decision`),
   бюджет автономности (`getAutonomyBudget`), ошибки автономности (`listAutonomyErrors`).
   Для каждого решения показываем `mode` и `escalation_reason`/`stop_reason` — «причина
   разрешения или запрета».
3. **Проверка результата** — таблица истории шагов: шаг, ожидаемый/фактический результат,
   время ответа (`duration_ms` + серверный `latency_ms` из `VisionResponse` при
   наличии), ошибки, пометка повтора (`duplicate`), итог сценария (счётчик ok/fail).
   Кнопка «Повторить сценарий» (reset + run).

Ограничения UI (документируем в подсказке вкладки):
- ожидания проверяют **поведение** (mode, статус, HTTP-код, отсутствие дублей), а не смысл
  `summary` от Vision — текст зависит от провайдера (echo/ollama/openai) и не детерминирован;
- `analysis_pending=true` при недоступном провайдере — это штатное поведение
  (`test_vision.py:197`), сценарий это показывает как факт, не как «успех агента».

## 6. Изменения в существующих файлах (минимум)

| Файл | Правка |
|---|---|
| `src/App.tsx` | +1 в union `Tab` (`"emulator"`), +1 пункт в `TABS` («Эмулятор и тесты»), +1 `<EmulatorView />` в `Shell()` |
| `src/lib/types.ts` | +экспорт типов `VirtualScreen`, `Scenario`, `StepResult` (или реэкспорт из `emulator/*`) — additive |
| `docs/release/vision-field-test.md` | +абзац: симулятор — способ прогнать полевой чек-лист Vision без человека |

Всё остальное — **новые файлы**:
`src/lib/emulator/{scene,screen,frameSource,scenario,scenarios,expectations,runner}.ts`,
`src/lib/emulator/__tests__` (node-тесты), `src/views/EmulatorView.tsx`.
Backend: правок нет. Миграций нет. Rust: правок нет.

## 7. Тесты

- **Node-тесты pure-логики** (паттерн `src/lib/activeTab.test.ts`, `llmStatus.test.ts`;
  держать вне tsc-scope — см. `tsconfig` exclude, иначе CI падает на `node:` без
  `@types/node`):
  - `buildScene`: портрет/ландшафт меняют размеры; разрешения из `RESOLUTIONS`;
    координаты — конечные числа; список команд непустой для всех 4 режимов экрана.
  - `expectations`: каждый предикат на ok/fail-случаях (включая 429/409 маппинг в
    человекочитаемый `actual`).
  - `scenarios`: валидность набора — известные `kind`, `expect.predicate` соответствует
    `kind` шага, уникальность `step.id`, покрыты все 8 обязательных сценариев.
- **Интеционная проверка цепочки (вручную + существующие тесты)**: существующие
  `tests/test_vision.py` (в т.ч. throttled/429) и `tests/test_safety_autonomous.py`
  доказывают, что цепочка, через которую идёт симулятор, реальная; новых backend-тестов
  Фаза 1 не требует. Если добавляем — `tests/test_emulator_chain.py`: FakeVisionProvider
  через `dependency_overrides[get_vision_gateway]` (паттерн `_use_gateway`), генератор
  кадра `png_bytes` из `test_vision.py`, прогон двух шагов сценария через API и assert
  `analysis_pending`/`summary`/`mode`.
- Критерий приёмки прогона: `pnpm build` ok; node-тесты зелёные; ручной прогон всех 8
  сценариев в приложении — итог фиксируется скриншотом панели результатов.

## 8. Риски и явные ограничения (проверить при реализации)

1. **Vision — не детерминирован.** Содержание `summary` зависит от провайдера. Ожидания
   сценариев — только поведенческие (§5). Нельзя assert'ить текст распознавания.
2. **Rate limit.** Прод-компоуза `MATCH_RATE_LIMIT_PER_MINUTE=60`. Длинные сценарии
   (8+ запросов) при повторных прогонах могут получить 429 — раннер обязан показывать
   http_status шага и не глотать 429 как «успех».
3. **Троттлинг Vision.** При `MATCH_VISION_MIN_INTERVAL_SECONDS > 0` часть кадров останется
   `analysis_pending=true` — это корректное поведение (throttled-тест), сценарий это
   отражает через `expectation=pending`.
4. **Размер кадра.** `captureVirtualFrame` должен отдавать PNG ≤ `MAX_FRAME_BYTES` (8 МиБ)
   и ширину ≤ 1280; иначе endpoint ответит 422 и шаг честно упадёт.
5. **Приватность.** Кадр не персистируется (метаданные + SHA-256, ADR-0007/0008) —
   не ослаблять; `source_label="emulator"` — свободная строка, новых полей не нужно.
6. **Фаза 2 (Android).** `adb screencap` → PNG → тот же `POST /api/v1/vision/observations`;
   отличаются только источник кадра и жесты. Схема сценария пригодна без изменений
   (шаги обращаются к `FrameSource`).

## 9. Порядок реализации (рекомендуемый)

1. `scene.ts` + `screen.ts` + рендер в `EmulatorView` + регистрация вкладки — кадр
   подтверждается вручную: `POST observation` из UI → `analysis_pending`/`summary` по факту
   провайдера.
2. `expectations.ts` + `scenario.ts` + 8 сценариев + node-тесты.
3. `runner.ts` + панель результатов + кнопки запуска/паузы/сброса + live-панель агента.
4. Ручной прогон всех сценариев на dev-стеке; фиксация итогов в
   `docs/release/acceptance-checklist.md`; `frameSource.ts`-заглушка на Фазу 2.

Итоговый артефакт: вкладка «Эмулятор и тесты» + 8 сценариев + прогон с доказательствами
в acceptance-checklist; backend-контракты не меняются.
