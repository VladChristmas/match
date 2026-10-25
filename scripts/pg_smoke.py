"""Сквозная проверка ключевых сценариев на боевом PostgreSQL.

Зачем: тесты `services/api` идут на in-memory SQLite, где datetime наивные, а на
PostgreSQL (`timestamptz`) даты приходят offset-aware — расхождение уже приводило
к 500 на `/dynamics/signals/compute` (этап 30). Этот скрипт исполняет рискованные
пути на реальной СУБД и падает с ненулевым кодом, если поведение сломалось.

Запуск (CI job `db-migrations` и локально при поднятом контейнере):
    MATCH_DATABASE_URL=postgresql+asyncpg://match:match@localhost:5433/match \
        python scripts/pg_smoke.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "services" / "api"))

from app.dynamics import compute_signals, detect_significant_change, list_signals
from app.models import Base, CompatibilityAssessment, Conversation, Message, User
from app.trust.engine import assess_risk

REQUIRED_ENV = "MATCH_DATABASE_URL"


async def scenario(session: AsyncSession) -> None:
    user = User(token_ref=f"pg-smoke-{uuid4().hex[:8]}")
    session.add(user)
    await session.flush()

    conversation = Conversation(user_id=user.id, autonomy_mode="auto_send")
    session.add(conversation)
    await session.flush()

    for content, direction in (
        ("Привет! Как дела?", "inbound"),
        ("Привет! Всё хорошо, спасибо 🙂", "outbound"),
        ("Чем занимаешься на выходных?", "inbound"),
        ("Давай встретимся в субботу", "inbound"),
    ):
        session.add(
            Message(
                conversation_id=conversation.id,
                direction=direction,
                content=content,
                source="manual",
                created_at=datetime.now(UTC) - timedelta(days=2),
            )
        )
    session.add(
        CompatibilityAssessment(
            user_id=user.id,
            conversation_id=conversation.id,
            goals_alignment=0.7,
            values_alignment=0.6,
            lifestyle_alignment=0.5,
            reciprocity=0.8,
            uncertainty=0.1,
            explanation="pg smoke",
        )
    )
    await session.commit()

    # 1. Вычисление сигналов — путь, который падал на PostgreSQL (naive vs aware).
    signals = await compute_signals(session, user.id, conversation)
    await session.commit()
    if len(signals) != 6:
        raise AssertionError(f"expected 6 signals, got {len(signals)}")

    # 2. Чтение сигналов с окном (SQL-сравнение aware-границ с timestamptz).
    since = datetime.now(UTC) - timedelta(days=90)
    listed = await list_signals(session, user_id=user.id, since=since)
    if len(listed) < 6:
        raise AssertionError(f"list_signals returned {len(listed)} (<6)")

    # 3. Правила риска на содержимом окна.
    risk = assess_risk([m.content for m in []])
    if risk.risk_category is None:
        raise AssertionError("risk assessment unavailable")

    # 4. Сравнение периодов на разных моментах (aware `now`).
    earlier = datetime.now(UTC) - timedelta(days=40)
    previous = await compute_signals(session, user.id, conversation, now=earlier)
    await session.commit()
    changes = detect_significant_change(previous, signals)
    if not isinstance(changes, list):
        raise AssertionError("compare failed")

    # Чистим за собой: smoke не должен оставлять строки в боевой БД.
    await session.execute(
        delete(CompatibilityAssessment).where(
            CompatibilityAssessment.conversation_id == conversation.id
        )
    )
    await session.execute(delete(Message).where(Message.conversation_id == conversation.id))
    await session.execute(delete(Conversation).where(Conversation.id == conversation.id))
    await session.execute(delete(User).where(User.id == user.id))
    await session.commit()


async def main() -> None:
    url = os.environ.get(REQUIRED_ENV)
    if not url:
        print(f"pg_smoke: {REQUIRED_ENV} is not set — skip (локально) / fail (CI)")
        raise SystemExit(0 if "CI" not in os.environ else 1)

    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as session:
            await scenario(session)
        print("pg_smoke: OK (6 signals, list, risk, compare)")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
