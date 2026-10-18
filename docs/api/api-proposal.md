# Предложение по API

Стиль: REST + OpenAPI, версия `/api/v1`. Контракты черновые.

## Профиль
- `GET /api/v1/profile`
- `PATCH /api/v1/profile`
- `GET /api/v1/profile/communication`
- `PATCH /api/v1/profile/communication`

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

## Анализ
- `POST /api/v1/analysis/psychology`
- `POST /api/v1/analysis/compatibility`
- `POST /api/v1/analysis/risk`

## Автономность
- `GET|PATCH /api/v1/agent/settings`
- `POST /api/v1/agent/pause`
- `POST /api/v1/agent/resume`
- `GET /api/v1/agent/actions`
- `POST /api/v1/agent/actions/{action_id}/approve`
- `POST /api/v1/agent/actions/{action_id}/reject`

## Интеграции
- `GET /api/v1/integrations`
- `GET /api/v1/integrations/{platform_id}/capabilities`
- `GET /api/v1/integrations/{platform_id}/status`
- `POST /api/v1/integrations/{platform_id}/disconnect`

## Приватность
- `GET /api/v1/privacy/export`
- `POST /api/v1/privacy/deletion-request`

## Общие требования к каждому маршруту

- Схемы запроса/ответа (Pydantic), авторизация по токену, права на объект (защита от IDOR).
- Коды ошибок, лимиты (rate limit), идемпотентность (`Idempotency-Key`) для действий.
- Пагинация, валидация, правила аудита, версия API.

## Запрет

Не создавать endpoint, позволяющий модели обходить `agent-runtime` и напрямую отправлять сообщения.
