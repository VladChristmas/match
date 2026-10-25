"""Тесты Relationship Dynamics (Этап 25, ADR-0031)."""

TOKEN_HEADER = {"X-Match-Token": "dynamics-user"}


async def _create_conversation(client, autonomy_mode="auto_send"):
    response = await client.post(
        "/api/v1/conversations",
        headers=TOKEN_HEADER,
        json={"autonomy_mode": autonomy_mode},
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _import_message(client, conversation_id, content, direction="inbound"):
    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/messages/import",
        headers=TOKEN_HEADER,
        json={"content": content, "direction": direction},
    )
    assert response.status_code == 201
    return response.json()


async def test_compute_signals(client):
    conversation_id = await _create_conversation(client)
    for text in ["Привет!", "Как дела?", "Чем занимаешься?"]:
        await _import_message(client, conversation_id, text, "inbound")
    await _import_message(client, conversation_id, "Привет! Всё хорошо.", "outbound")

    computed = await client.post(
        f"/api/v1/dynamics/signals/compute?conversation_id={conversation_id}",
        headers=TOKEN_HEADER,
    )
    assert computed.status_code == 200
    body = computed.json()
    assert len(body) == 6  # шесть измерений
    dimensions = {s["dimension"] for s in body}
    assert dimensions == {
        "reciprocity",
        "consistency",
        "emotional_comfort",
        "expectation_alignment",
        "agreement_ability",
        "relationship_development",
    }
    for signal in body:
        assert 0.0 <= signal["value"] <= 1.0
        assert "evidence" in signal
        assert "observed_at" in signal


async def test_list_signals(client):
    conversation_id = await _create_conversation(client)
    await _import_message(client, conversation_id, "Привет!", "inbound")
    await client.post(
        f"/api/v1/dynamics/signals/compute?conversation_id={conversation_id}",
        headers=TOKEN_HEADER,
    )

    listed = await client.get(
        "/api/v1/dynamics/signals",
        headers=TOKEN_HEADER,
        params={"conversation_id": conversation_id},
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 6


async def test_list_signals_by_dimension(client):
    conversation_id = await _create_conversation(client)
    await _import_message(client, conversation_id, "Привет!", "inbound")
    await client.post(
        f"/api/v1/dynamics/signals/compute?conversation_id={conversation_id}",
        headers=TOKEN_HEADER,
    )

    listed = await client.get(
        "/api/v1/dynamics/signals",
        headers=TOKEN_HEADER,
        params={"conversation_id": conversation_id, "dimension": "reciprocity"},
    )
    assert listed.status_code == 200
    assert all(s["dimension"] == "reciprocity" for s in listed.json())


async def test_compare_periods(client):
    conversation_id = await _create_conversation(client)
    for text in ["Привет!", "Как дела?", "Чем занимаешься?", "Давай встретимся"]:
        await _import_message(client, conversation_id, text, "inbound")
    await client.post(
        f"/api/v1/dynamics/signals/compute?conversation_id={conversation_id}",
        headers=TOKEN_HEADER,
    )

    compared = await client.get(
        "/api/v1/dynamics/compare",
        headers=TOKEN_HEADER,
        params={"conversation_id": conversation_id, "days": 30},
    )
    assert compared.status_code == 200
    assert isinstance(compared.json(), list)


async def test_turning_point_timeline(client):
    conversation_id = await _create_conversation(client)
    await _import_message(client, conversation_id, "Привет!", "inbound")
    await client.post(
        f"/api/v1/dynamics/signals/compute?conversation_id={conversation_id}",
        headers=TOKEN_HEADER,
    )

    created = await client.post(
        "/api/v1/dynamics/timeline",
        headers=TOKEN_HEADER,
        params={
            "conversation_id": conversation_id,
            "event_type": "boundary_set",
            "description": "Пользователь обозначил границу общения",
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["event_type"] == "boundary_set"
    assert body["description"] == "Пользователь обозначил границу общения"
    assert "signals_before" in body
    assert "signals_after" in body

    listed = await client.get(
        "/api/v1/dynamics/timeline",
        headers=TOKEN_HEADER,
        params={"conversation_id": conversation_id},
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1


async def test_foreign_conversation_404(client):
    # Свой разговор
    await _create_conversation(client)
    # Чужой разговор (другой токен)
    theirs = await client.post(
        "/api/v1/conversations",
        headers={"X-Match-Token": "other-user"},
        json={"autonomy_mode": "auto_send"},
    )
    theirs_id = theirs.json()["id"]

    response = await client.post(
        f"/api/v1/dynamics/signals/compute?conversation_id={theirs_id}",
        headers=TOKEN_HEADER,
    )
    assert response.status_code == 404

    response = await client.get(
        "/api/v1/dynamics/signals",
        headers=TOKEN_HEADER,
        params={"conversation_id": theirs_id},
    )
    assert response.status_code == 200
    assert response.json() == []


async def test_detect_significant_change():
    from app.dynamics import detect_significant_change

    previous = [
        type("S", (), {"dimension": "reciprocity", "value": 0.5})(),
        type("S", (), {"dimension": "emotional_comfort", "value": 0.8})(),
    ]
    current = [
        type("S", (), {"dimension": "reciprocity", "value": 0.3})(),
        type("S", (), {"dimension": "emotional_comfort", "value": 0.4})(),
    ]
    changes = detect_significant_change(previous, current)
    assert len(changes) == 2
    assert changes[0]["dimension"] == "reciprocity"
    assert changes[0]["delta"] == -0.2
    assert changes[0]["direction"] == "declined"
    assert changes[1]["dimension"] == "emotional_comfort"
    assert changes[1]["delta"] == -0.4
    assert changes[1]["direction"] == "declined"


async def test_detect_no_change_below_threshold():
    from app.dynamics import detect_significant_change

    previous = [type("S", (), {"dimension": "reciprocity", "value": 0.5})()]
    current = [type("S", (), {"dimension": "reciprocity", "value": 0.35})()]
    changes = detect_significant_change(previous, current)
    assert changes == []


def test_as_utc_normalizes_naive_and_aware():
    """Naive/aware-даты: PostgreSQL отдаёт aware, SQLite — naive; окно сравнимо в обоих."""
    from datetime import UTC, datetime, timedelta

    from app.dynamics.service import _as_utc

    naive = datetime(2026, 10, 25, 12, 0, 0)
    aware = datetime(2026, 10, 25, 15, 0, 0, tzinfo=UTC)
    assert _as_utc(naive) == naive.replace(tzinfo=UTC)
    assert _as_utc(aware) == aware
    assert _as_utc(aware).tzinfo is not None
    assert _as_utc(None) is None
    # Наивная дата из SQLite сравнивается с aware-окном (регрессия PG: TypeError).
    window_start = aware - timedelta(days=90)
    assert _as_utc(naive) >= window_start
