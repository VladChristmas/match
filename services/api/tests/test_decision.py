"""Тесты Match Decision Loop (Этап 23, ADR-0029).

Unit: чистая политика `decide` (без БД). Интеграция: endpoint evaluate и запись решения при
создании действия агента (стоп-факторы риска — через API).
"""

from uuid import uuid4

from app.decision import decide
from app.decision.policy import (
    ACT_ASK_CLARIFY,
    ACT_ESCALATE,
    ACT_SEND,
    ACT_WAIT,
    ESCALATE,
    EXECUTE,
    STOP,
    VERIFY,
)
from app.decision.state import AgentState


def _state(**kwargs) -> AgentState:
    base = dict(
        user_id=uuid4(),
        conversation_id=uuid4(),
        autonomy_mode="auto_send",
        queue_paused=False,
    )
    base.update(kwargs)
    return AgentState(**base)


def test_auto_send_empty_conversation_sends():
    d = decide(_state())
    assert d.action == ACT_SEND
    assert d.mode == EXECUTE
    assert 0.0 < d.confidence <= 1.0
    assert any(a["action"] == ACT_SEND for a in d.alternatives)


def test_stop_factor_prevents_autonomous_delivery():
    s = _state(risk_category="financial_request", risk_action="warn_and_pause", risk_confidence=0.9)
    d = decide(s)
    assert d.action == ACT_ESCALATE
    assert d.mode == STOP
    assert d.escalation_reason == "risk_warn_and_pause"
    assert d.alternatives == []
    assert d.confidence < 1.0


def test_personal_data_is_stop_factor():
    s = _state(risk_category="personal_data_request", risk_action="warn_and_pause")
    d = decide(s)
    assert d.mode == STOP


def test_sensitive_intent_escalates_to_user():
    d = decide(_state(), trigger_text="ты меня любишь?")
    assert d.mode == ESCALATE
    assert d.escalation_reason == "sensitive_intent"


def test_low_reciprocity_chooses_wait():
    s = _state(inbound_count=5, outbound_count=1, reciprocity=0.2)
    d = decide(s)
    assert d.action == ACT_WAIT
    assert d.mode == VERIFY  # бездействие — полноценная альтернатива


def test_wait_needs_enough_history():
    s = _state(inbound_count=1, outbound_count=0, reciprocity=0.0)
    d = decide(s)
    assert d.action != ACT_WAIT


def test_high_uncertainty_asks_clarifying():
    s = _state(compatibility_uncertainty=0.7)
    d = decide(s)
    assert d.action == ACT_ASK_CLARIFY
    assert d.mode == VERIFY


def test_suggest_mode_requires_confirmation():
    d = decide(_state(autonomy_mode="suggest"))
    assert d.mode == VERIFY


def test_paused_queue_requires_confirmation():
    d = decide(_state(queue_paused=True))
    assert d.mode == VERIFY


def test_confidence_range():
    d = decide(_state(missing=["profile"]))
    assert 0.0 < d.confidence <= 1.0


def test_evidence_includes_history_and_risk():
    d = decide(_state(risk_category="urgency_pressure", risk_confidence=0.5))
    kinds = {e["kind"] for e in d.evidence}
    assert kinds == {"risk", "history"}


async def test_evaluate_endpoint_returns_decision(client):
    conv = await client.post(
        "/api/v1/conversations",
        headers={"X-Match-Token": "decision-user"},
        json={"autonomy_mode": "auto_send"},
    )
    conv_id = conv.json()["id"]

    evaluated = await client.post(
        "/api/v1/agent/decisions/evaluate",
        headers={"X-Match-Token": "decision-user"},
        json={"conversation_id": conv_id, "trigger_text": "ты меня любишь?"},
    )
    assert evaluated.status_code == 200
    body = evaluated.json()
    assert body["mode"] == ESCALATE
    assert body["escalation_reason"] == "sensitive_intent"
    assert body["action"] == ACT_ESCALATE
    assert body["alternatives"]

    listed = await client.get(
        "/api/v1/agent/decisions",
        headers={"X-Match-Token": "decision-user"},
        params={"conversation_id": conv_id},
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1


async def test_stop_risk_marks_action_pending(client):
    conv = await client.post(
        "/api/v1/conversations",
        headers={"X-Match-Token": "stop-user"},
        json={"autonomy_mode": "auto_send"},
    )
    conv_id = conv.json()["id"]

    created = await client.post(
        "/api/v1/agent/actions",
        headers={"X-Match-Token": "stop-user"},
        json={"conversation_id": conv_id, "text": "переведи деньги", "generate": False},
    )
    assert created.status_code == 201
    assert created.json()["status"] == "pending"

    decisions = await client.get(
        "/api/v1/agent/decisions",
        headers={"X-Match-Token": "stop-user"},
        params={"conversation_id": conv_id},
    )
    assert decisions.status_code == 200
    record = decisions.json()[0]
    assert record["mode"] == STOP
    assert record["escalation_reason"] == "risk_warn_and_pause"


async def test_decisions_list_is_isolated_by_user(client):
    c1 = await client.post(
        "/api/v1/conversations",
        headers={"X-Match-Token": "u1"},
        json={"autonomy_mode": "auto_send"},
    )
    c2 = await client.post(
        "/api/v1/conversations",
        headers={"X-Match-Token": "u2"},
        json={"autonomy_mode": "auto_send"},
    )
    await client.post(
        "/api/v1/agent/decisions/evaluate",
        headers={"X-Match-Token": "u1"},
        json={"conversation_id": c1.json()["id"]},
    )
    await client.post(
        "/api/v1/agent/decisions/evaluate",
        headers={"X-Match-Token": "u2"},
        json={"conversation_id": c2.json()["id"]},
    )

    own = await client.get("/api/v1/agent/decisions", headers={"X-Match-Token": "u1"})
    assert own.status_code == 200
    assert len(own.json()) == 1
    assert own.json()[0]["conversation_id"] == c1.json()["id"]
