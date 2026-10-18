# services/

Серверные сервисы (Python + FastAPI).

- `api/` — REST API `/api/v1` для клиента (FastAPI). Этап 1: `/health`, `/health/ready`, PostgreSQL, Alembic-миграции.
- `agent-runtime/` — центральный контроллер автономности: очередь событий, планировщик, проверка разрешений, идемпотентность.
