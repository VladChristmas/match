import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.agent.worker import deliver_due
from app.models import AgentAction

TOKEN_HEADER = {"X-Match-Token": "worker-user"}


async def _scheduled_action(client, delay: int = 60) -> tuple[str, str]:
    conversation = await client.post(
        "/api/v1/conversations",
        headers=TOKEN_HEADER,
        json={"autonomy_mode": "auto_send"},
    )
    conversation_id = conversation.json()["id"]
    created = await client.post(
        "/api/v1/agent/actions",
        headers=TOKEN_HEADER,
        json={
            "conversation_id": conversation_id,
            "text": "Привет!",
            "generate": False,
            "schedule_in_seconds": delay,
        },
    )
    assert created.status_code == 201
    return created.json()["id"], conversation_id


async def test_scheduled_action_waits_until_due(client, engine):
    action_id, conversation_id = await _scheduled_action(client, delay=60)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async with maker() as session:
        action = await session.get(AgentAction, uuid.UUID(action_id))
        assert action.status == "scheduled"
        assert action.scheduled_at is not None
        assert await deliver_due(session, now=datetime.now(UTC)) == 0

    async with maker() as session:
        action = await session.get(AgentAction, uuid.UUID(action_id))
        assert action.status == "scheduled"

    async with maker() as session:
        assert await deliver_due(session, now=datetime.now(UTC) + timedelta(minutes=5)) == 1

    async with maker() as session:
        action = await session.get(AgentAction, uuid.UUID(action_id))
        assert action.status == "sent"
        assert action.sent_at is not None
        assert action.scheduled_at is None

    messages = await client.get(
        f"/api/v1/conversations/{conversation_id}/messages", headers=TOKEN_HEADER
    )
    outbound = [item for item in messages.json() if item["direction"] == "outbound"]
    assert len(outbound) == 1
    assert outbound[0]["source"] == "agent"


async def test_failed_delivery_backs_off_then_fails(client, engine):
    action_id, _ = await _scheduled_action(client, delay=60)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    moment = datetime.now(UTC) + timedelta(minutes=5)

    async def boom(session, action):
        raise RuntimeError("network down")

    async with maker() as session:
        assert (
            await deliver_due(session, now=moment, deliver=boom, max_attempts=2, backoff_seconds=10)
            == 0
        )

    async with maker() as session:
        action = await session.get(AgentAction, uuid.UUID(action_id))
        assert action.status == "scheduled"
        assert action.attempts == 1
        assert action.error == "network down"

    second_moment = moment + timedelta(seconds=10)
    async with maker() as session:
        assert (
            await deliver_due(
                session, now=second_moment, deliver=boom, max_attempts=2, backoff_seconds=10
            )
            == 0
        )

    async with maker() as session:
        action = await session.get(AgentAction, uuid.UUID(action_id))
        assert action.status == "failed"
        assert action.attempts == 2
        assert action.next_attempt_at is None


async def test_scheduling_requires_auto_send(client):
    conversation = await client.post(
        "/api/v1/conversations",
        headers=TOKEN_HEADER,
        json={"autonomy_mode": "suggest"},
    )
    conversation_id = conversation.json()["id"]
    created = await client.post(
        "/api/v1/agent/actions",
        headers=TOKEN_HEADER,
        json={
            "conversation_id": conversation_id,
            "text": "hi",
            "generate": False,
            "schedule_in_seconds": 60,
        },
    )
    assert created.status_code == 201
    assert created.json()["status"] == "pending"


async def test_zero_delay_sends_immediately(client):
    conversation = await client.post(
        "/api/v1/conversations",
        headers=TOKEN_HEADER,
        json={"autonomy_mode": "auto_send"},
    )
    conversation_id = conversation.json()["id"]
    created = await client.post(
        "/api/v1/agent/actions",
        headers=TOKEN_HEADER,
        json={
            "conversation_id": conversation_id,
            "text": "hi",
            "generate": False,
            "schedule_in_seconds": 0,
        },
    )
    assert created.status_code == 201
    assert created.json()["status"] == "sent"
