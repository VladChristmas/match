# Предложение по API

Стиль: REST + OpenAPI, версия `/api/v1`. Контракты черновые.

> Авторизация: `Authorization: Bearer <token>` либо `X-Match-Token: <token>`.
> Реализация Этапа 2 — временная (см. ADR-0010), финализация механизма токенов — OQ-7.

## Профиль
- `GET /api/v1/profile` — профиль пользователя (создаётся по умолчанию при первом запросе)
- `PATCH /api/v1/profile` — частичное обновление (инкремент `profile_version`)
- `GET /api/v1/profile/communication` — профиль общения
- `PATCH /api/v1/profile/communication` — частичное обновление (инкремент `version`)

## Обратная связь
- `POST /api/v1/feedback` — сохранить отзыв (`feedback_type`, `rating` 1–5, `correction`)
- `GET /api/v1/feedback` — список отзывов пользователя (пагинация `limit`/`offset`)

## Знакомства
- `GET|POST /api/v1/matches`
- `GET|PATCH|DELETE /api/v1/matches/{match_id}`

## Диалоги
- `GET|POST /api/v1/conversations`
- `GET /api/v1/conversations/{conversation_id}`
- `GET /api/v1/conversations/{conversation_id}/messages`
- `POST /api/v1/conversations/{conversation_id}/messages/import`
- `POST /api/v1/conversations/{conversation_id}/analyze`
- `POST /api/v1/conversations/{conversation_id}/drafts`

> Этап 3: `/drafts` возвращает черновик и результат валидации, но **не отправляет** сообщение
> (соблюдение запрета ниже: LLM не выполняет действия напрямую). Автоотправка — Этап 8.
> Этап 6: `/drafts` может вернуть `503` (нет доступного LLM-провайдера) или `429` (лимит запросов).

## Анализ
- `POST /api/v1/analysis/psychology`
- `POST /api/v1/analysis/compatibility`
- `POST /api/v1/analysis/risk`

> Этап 4: `compatibility` и `risk` реализованы (детерминированные эвристики, `model_version=heuristic-1.0`),
> плюс списки `GET /api/v1/analysis/compatibility` и `GET /api/v1/analysis/risk`.
> Оценки раздельные и объяснимые; психопрофиль (`psychology`) — отдельный модуль, пока не реализован.

## Автономность
- `GET|PATCH /api/v1/agent/settings`
- `POST /api/v1/agent/pause`
- `POST /api/v1/agent/resume`
- `GET /api/v1/agent/actions`
- `POST /api/v1/agent/actions/{action_id}/approve`
- `POST /api/v1/agent/actions/{action_id}/reject`

> Этап 8: реализованы (ADR-0015). Добавлен `POST /api/v1/agent/actions` (поставить действие в
> очередь; заголовок `Idempotency-Key`). `auto_send` доставляет сразу, иные режимы/пауза → `pending`
> (передача человеку: `approve`/`reject`). «Доставка» = исходящее сообщение `source=agent`.

## Интеграции
- `GET /api/v1/integrations`
- `GET /api/v1/integrations/{platform_id}/capabilities`
- `GET /api/v1/integrations/{platform_id}/status`
- `POST /api/v1/integrations/{platform_id}/disconnect`

> Этап 7: реализованы. Разрешена только интеграция `manual_import` (ручной импорт, см.
> `POST /api/v1/conversations/{id}/messages/import`). Известные площадки (Tinder, Badoo, Bumble,
> OkCupid, Hinge, Мамба) возвращают статус `unsupported` и нулевые возможности — имитация
> подключения не допускается. `disconnect` для неподдержанной площадки → `409`.
> Контракт адаптера и contract-тесты — `app/integrations/`, `tests/test_integrations.py` (ADR-0014).

## Приватность
- `GET /api/v1/privacy/export`
- `POST /api/v1/privacy/deletion-request`

> Этап 9: реализованы (ADR-0016). `export` отдаёт все данные пользователя одним JSON
> (`token_ref` редактируется), `deletion-request` удаляет данные пользователя (явный порядок
> удаления, не полагается на FK-каскад). Ограничение нагрузки `MATCH_RATE_LIMIT_PER_MINUTE`
> (0 = выключено) применяется к `/drafts` и `/agent/actions`; при превышении — `429`.

## Зрение (vision)
- `GET /api/v1/vision/observations`
- `POST /api/v1/vision/observations`

> Этап 10: реализованы (ADR-0017). Приём кадра наблюдения из клиента (`Windows.Graphics.Capture`).
> Кадр — PNG (base64), сервер проверяет формат и лимит размера и **не сохраняет изображение**,
> только метаданные (размеры, байты, SHA-256, метка источника, время). Изображения нет в
> экспорте/удалении, кроме метаданных наблюдений.
> Этап 11: при приёме выполняется анализ кадров моделью (ADR-0018) — `analyze=true` по умолчанию.
> Провайдер задаётся `MATCH_VISION_PROVIDER` (по умолчанию локальный `ollama`), результат пишется
> в `summary`/`provider`/`model` + `ModelRun`; при недоступной модели наблюдение сохраняется с
> `analysis_pending=true` (кадр не хранится, поэтому повторный анализ = повторная отправка кадра).

## Токены доступа
- `GET /api/v1/tokens`
- `POST /api/v1/tokens`
- `POST /api/v1/tokens/{token_id}/rotate`
- `DELETE /api/v1/tokens/{token_id}`

> Этап 12: реализованы (ADR-0019). Закрывает OQ-7. Токен генерируется сервером
> (`secrets.token_urlsafe`, префикс `match_`), отдаётся один раз при выдаче; в БД хранится
> только SHA-256 хэш. `GET` отдаёт метаданные без секретов, `rotate` отзывает старый и выдаёт
> новую пару, `DELETE` отзывает. Все операции ограничены владельцем. Легаси-схема `token_ref`
> (ADR-0010) сохранена для разработки и отключается `MATCH_AUTH_ALLOW_LEGACY_TOKENS=false`;
> выданные (в т.ч. отозванные) токены в легаси-путь не попадают. Метаданные токенов входят в
> экспорт приватности (без хэша) и удаляются при удалении аккаунта.

## Общие требования к каждому маршруту

- Схемы запроса/ответа (Pydantic), авторизация по токену, права на объект (защита от IDOR).
- Коды ошибок, лимиты (rate limit), идемпотентность (`Idempotency-Key`) для действий.
- Пагинация, валидация, правила аудита, версия API.

## Запрет

Не создавать endpoint, позволяющий модели обходить `agent-runtime` и напрямую отправлять сообщения.
