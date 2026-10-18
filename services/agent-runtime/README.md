# agent-runtime

Внешний воркер автономности MATCH (Этап 21, ADR-0027). Доставляет отложенные действия
агента (`agent_actions.status = "scheduled"`) в назначенное время, с повторными попытками
и линейным backoff.

## Запуск

Из каталога `services/api` (там venv с зависимостями и `.env`):

```powershell
services\api\.venv\Scripts\python.exe services\agent-runtime\main.py
```

Воркер подключается к той же БД (`MATCH_DATABASE_URL`) и настройкам, что API. Перед
запуском примените миграции: `alembic upgrade head`.

## Настройки

| Переменная | По умолчанию | Значение |
|---|---|---|
| `MATCH_AGENT_WORKER_INTERVAL_SECONDS` | 15 | период опроса очереди |
| `MATCH_AGENT_MAX_ATTEMPTS` | 5 | попыток до статуса `failed` |
| `MATCH_AGENT_RETRY_BACKOFF_SECONDS` | 30 | база линейного backoff (×номер попытки) |

## Жизненный цикл действия

`agent_actions.status`: `pending` (ждёт человека) → `sent`; либо `scheduled`
(ждёт `scheduled_at`) → `sent`; при ошибках `scheduled` сохраняется, `attempts`
растёт, `next_attempt_at` отодвигается; после лимита — `failed`.

Действия создаются через `POST /api/v1/agent/actions` с `schedule_in_seconds > 0`
(работает для разговоров в режиме `auto_send` и при снятой паузе).
