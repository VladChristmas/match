# infra/

Инфраструктура.

- `docker-compose.yml` — локальные сервисы (PostgreSQL + api). Запуск: `docker compose -f infra/docker-compose.yml up --build`.
- `deployment/` — конфигурации развёртывания.
- `monitoring/` — метрики и алерты.
