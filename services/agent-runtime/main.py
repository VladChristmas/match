"""Отдельный процесс воркера автономности MATCH (Этап 21, ADR-0027).

Запускает цикл `app.agent.worker.run_forever`, используя код и зависимости сервиса
`services/api` (тот же venv и `MATCH_DATABASE_URL`). Процесс можно масштабировать
горизонтально: каждое действие блокируется статусом `scheduled` и коммитится отдельно.

Запуск (из каталога `services/api`, чтобы venv и `.env` были доступны):

    .\.venv\Scripts\python.exe ..\agent-runtime\main.py

Переменные окружения: `MATCH_AGENT_WORKER_INTERVAL_SECONDS` (по умолчанию 15),
`MATCH_AGENT_MAX_ATTEMPTS` (5), `MATCH_AGENT_RETRY_BACKOFF_SECONDS` (30).
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "api"))

from app.agent.worker import main  # noqa: E402

if __name__ == "__main__":
    main()
