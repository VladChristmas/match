"""Внешний воркер автономности (Этап 21, ADR-0027).

Доставляет отложенные действия агента (`agent_actions.status == "scheduled"`) в момент
`scheduled_at`. При ошибке увеличивает счётчик попыток и назначает `next_attempt_at` по
линейному backoff; после `MATCH_AGENT_MAX_ATTEMPTS` переводит действие в `failed`. Каждое
действие коммитится отдельно, поэтому воркер не блокирует пользовательские запросы и
переживает перезапуск. Запускается отдельным процессом `services/agent-runtime`.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agent.service import FAILED, SCHEDULED, _deliver
from app.config import get_settings
from app.db import SessionLocal
from app.models import AgentAction, Conversation

logger = logging.getLogger("match.agent_runtime")

DeliverFn = Callable[[AsyncSession, AgentAction], Awaitable[None]]


async def _deliver_scheduled(session: AsyncSession, action: AgentAction) -> None:
    conversation = await session.get(Conversation, action.conversation_id)
    if conversation is None:
        raise RuntimeError("conversation not found")
    await _deliver(session, conversation, action)
    action.scheduled_at = None
    action.next_attempt_at = None
    action.error = None


async def deliver_due(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    deliver: DeliverFn | None = None,
    max_attempts: int | None = None,
    backoff_seconds: float | None = None,
) -> int:
    """Доставляет все просроченные отложенные действия. Возвращает число доставленных."""
    settings = get_settings()
    moment = now or datetime.now(UTC)
    attempt_fn = deliver or _deliver_scheduled
    limit = max_attempts if max_attempts is not None else settings.agent_max_attempts
    backoff = settings.agent_retry_backoff_seconds if backoff_seconds is None else backoff_seconds

    due = list(
        await session.scalars(
            select(AgentAction)
            .where(
                AgentAction.status == SCHEDULED,
                AgentAction.next_attempt_at.is_not(None),
                AgentAction.next_attempt_at <= moment,
            )
            .order_by(AgentAction.next_attempt_at.asc())
        )
    )

    delivered = 0
    for action in due:
        try:
            await attempt_fn(session, action)
        except Exception as exc:  # noqa: BLE001 - одна ошибка не должна ронять обработку
            attempts = (action.attempts or 0) + 1
            action.attempts = attempts
            action.error = str(exc)
            if attempts >= limit:
                action.status = FAILED
                action.next_attempt_at = None
                logger.warning(
                    "action %s failed permanently after %s attempts", action.id, attempts
                )
            else:
                action.status = SCHEDULED
                action.next_attempt_at = moment + timedelta(seconds=backoff * attempts)
                logger.warning("action %s failed (attempt %s): %s", action.id, attempts, exc)
        else:
            delivered += 1
            logger.info("action %s delivered", action.id)
        await session.commit()

    if due:
        logger.info("deliver_due: %s/%s delivered", delivered, len(due))
    return delivered


async def run_forever(
    interval_seconds: float | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    settings = get_settings()
    interval = interval_seconds or settings.agent_worker_interval_seconds
    factory = session_factory or SessionLocal
    logger.info("agent-runtime started (interval=%ss)", interval)
    while True:
        try:
            async with factory() as session:
                await deliver_due(session)
        except Exception:  # noqa: BLE001 - цикл не должен прерываться
            logger.exception("deliver_due crashed")
        await asyncio.sleep(interval)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(run_forever())


if __name__ == "__main__":
    main()
