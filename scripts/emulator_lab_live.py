#!/usr/bin/env python3
"""Живой прогон сценариев лаборатории «Эмулятор и тесты» через РЕАЛЬНЫЙ HTTP API.

Зеркало `apps/desktop/src/lib/emulator/scenarios.ts` (ТЗ docs/testing/emulator-lab-spec.md §4):
те же шаги и те же ожидания, но без GUI — для CI/регламента и доказательства в
acceptance-checklist. Кадр — настоящий PNG (генератор как в tests/), поступает в
`POST /api/v1/vision/observations` (analyze=true); агент — через реальные
decisions/actions/budget.

Ожидания поведенческие: vision-pending при недоступном провайдере — корректный
результат (как test_vision.py:197), а не «зелёный» успех.

Запуск:
    MATCH_BASE_URL=http://127.0.0.1:8000 MATCH_TOKEN=<token> python scripts/emulator_lab_live.py
"""

from __future__ import annotations

import base64
import os
import struct
import sys
import time
import uuid
import zlib

import httpx

BASE_URL = os.environ.get("MATCH_BASE_URL", "http://127.0.0.1:8000")
TOKEN = os.environ.get("MATCH_TOKEN", "emulator-lab")
TIMEOUT = 20.0

results: list[tuple[str, str, str, str, bool]] = []


def png_b64(width: int = 360, height: int = 640) -> str:
    """Настоящий PNG (как tests/test_vision.py) — проходит decode_png_frame."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    row = b"\x00" + b"\x20\x30\x50" * width
    idat = chunk(b"IDAT", zlib.compress(row * height, 9))
    iend = chunk(b"IEND", b"")
    return base64.b64encode(signature + ihdr + idat + iend).decode()


def call(
    method: str,
    path: str,
    *,
    json: dict | None = None,
    key: str | None = None,
) -> tuple[int, dict | list | None]:
    headers = {"Authorization": f"Bearer {TOKEN}"}
    if key:
        headers["Idempotency-Key"] = key
    response = httpx.request(
        method,
        f"{BASE_URL}{path}",
        json=json,
        headers=headers,
        timeout=TIMEOUT,
    )
    data = response.json() if response.text else None
    return response.status_code, data


def check(name: str, expected: str, ok: bool, actual: str = "") -> None:
    results.append((name, expected, actual or str(ok), "ok" if ok else "FAIL", ok))


def conversation(autonomy: str = "auto_send") -> str:
    status, data = call("POST", "/api/v1/conversations", json={"autonomy_mode": autonomy})
    assert status == 201, f"conversation: {status} {data}"
    return data["id"]


def import_message(conv: str, text: str, direction: str = "inbound") -> int:
    status, _ = call(
        "POST",
        f"/api/v1/conversations/{conv}/messages/import",
        json={"content": text, "direction": direction, "source": "emulator-live"},
    )
    return status


def evaluate(conv: str, text: str | None) -> tuple[int, str]:
    payload: dict = {"conversation_id": conv}
    if text:
        payload["trigger_text"] = text
    status, data = call("POST", "/api/v1/agent/decisions/evaluate", json=payload)
    return status, (data or {}).get("mode", "")


def create_action(conv: str, key: str) -> tuple[int, dict]:
    return call(
        "POST",
        "/api/v1/agent/actions",
        json={"conversation_id": conv, "generate": True},
        key=key,
    )


def emulator_actions(conv: str, scenario: str) -> list[dict]:
    status, data = call("GET", "/api/v1/agent/actions?limit=200")
    assert status == 200, f"actions: {status}"
    prefix = f"match-emu-{scenario}-"
    return [
        item
        for item in data or []
        if item.get("conversation_id") == conv
        and str(item.get("idempotency_key") or "").startswith(prefix)
    ]


def budget() -> dict:
    status, data = call("GET", "/api/v1/autonomy/budget")
    assert status == 200, f"budget: {status}"
    return data


def set_budget(**patch: object) -> int:
    status, _ = call("PATCH", "/api/v1/autonomy/budget", json=patch)
    return status


def scenario_new_match() -> None:
    name = "1. new_match_first_message"
    conv = conversation()
    status, data = call(
        "POST",
        "/api/v1/vision/observations",
        json={
            "conversation_id": conv,
            "frame_base64": png_b64(),
            "source_label": "emulator-live",
            "captured_at": "2026-10-30T12:00:00Z",
            "analyze": True,
        },
    )
    pending = (data or {}).get("analysis_pending")
    check(f"{name}: observation", "201", status == 201, str(status))
    check(f"{name}: analysis_pending", "провайдер недоступен → pending (ожидаемо)", pending is True, str(pending))
    check(f"{name}: import", "201", import_message(conv, "Привет! Как дела?") == 201)
    eval_status, mode = evaluate(conv, "Привет! Как дела?")
    check(f"{name}: evaluate mode", "execute/verify/escalate", eval_status == 200 and mode in {"execute", "verify", "escalate"}, mode)
    status, action = create_action(conv, f"match-emu-{uuid.uuid4().hex[:8]}-a")
    check(f"{name}: create_action", "201 без дубля", status == 201, str(status))
    check(f"{name}: статус действия", "sent/pending", action["status"] in {"sent", "pending"}, action["status"])


def scenario_continue_with_memory() -> None:
    name = "2. continue_with_memory"
    conv = conversation()
    for text, direction in [
        ("Привет! Только вернулась с прогулки)", "inbound"),
        ("Здорово. Что любишь делать на выходных?", "outbound"),
        ("Люблю горные походы и кофе)", "inbound"),
    ]:
        assert import_message(conv, text, direction) == 201
    status, _ = call(
        "POST",
        "/api/v1/vision/observations",
        json={
            "conversation_id": conv,
            "frame_base64": png_b64(),
            "source_label": "emulator-live",
            "captured_at": "2026-10-30T12:01:00Z",
            "analyze": True,
        },
    )
    check(f"{name}: observation", "201", status == 201, str(status))
    followup = "Кстати, помнишь, я говорила про походы? Расскажи про свой последний)"
    assert import_message(conv, followup) == 201
    eval_status, mode = evaluate(conv, followup)
    check(f"{name}: evaluate mode", "execute/verify", eval_status == 200 and mode in {"execute", "verify"}, mode)


def _sensitive(name: str, seed: list[tuple[str, str]], trigger: str | None) -> None:
    conv = conversation()
    for text, direction in seed:
        assert import_message(conv, text, direction) == 201
    eval_status, mode = evaluate(conv, trigger)
    check(
        f"{name}: evaluate mode",
        "escalate/verify (авто-отправки нет)",
        eval_status == 200 and mode in {"escalate", "verify"},
        mode,
    )
    status, action = create_action(conv, f"match-emu-{uuid.uuid4().hex[:8]}-a")
    check(f"{name}: действие", "201", status == 201, str(status))
    check(f"{name}: статус", "pending", action["status"] == "pending", action["status"])


def scenario_ambiguous() -> None:
    # Полная семантика: reciprocity < 0.4 при входящих без ответа → wait, не send
    # (см. tests/test_safety_autonomous.py и decide() шаг 5).
    _sensitive(
        "3. ambiguous_message",
        [
            ("ага", "inbound"),
            ("не знаю", "inbound"),
            ("мб", "inbound"),
        ],
        None,
    )


def scenario_boundaries() -> None:
    # Обязательства → ESCALATION_PATTERNS → escalate (sensitive_intent).
    _sensitive(
        "4. boundaries_and_loss_of_interest",
        [
            ("Эй, давно не пишу. Как дела?", "outbound"),
            ("Извини, мне не интересно общение. Давай не будем продолжать.", "inbound"),
            ("Давай только мы, официально?", "inbound"),
        ],
        "Давай только мы, официально?",
    )


def scenario_similar_names() -> None:
    name = "5. context_loss_similar_names"
    conv1 = conversation()
    conv2 = conversation()
    assert import_message(conv1, "Привет! Рада слышать)") == 201
    assert import_message(conv2, "Да, тут. Что нового?") == 201
    status1, action1 = create_action(conv1, f"match-emu-{uuid.uuid4().hex[:8]}-1")
    status2, action2 = create_action(conv2, f"match-emu-{uuid.uuid4().hex[:8]}-2")
    check(f"{name}: действия", "201/201", status1 == 201 and status2 == 201, f"{status1}/{status2}")
    check(
        f"{name}: привязка к верному диалогу",
        "conv1/conv2 разделены",
        action1["conversation_id"] == conv1 and action2["conversation_id"] == conv2,
        f"{action1['conversation_id'][:8]}/{action2['conversation_id'][:8]}",
    )


def scenario_pause_cancel() -> None:
    name = "6. pause_cancel_restart"
    conv = conversation()
    assert import_message(conv, "Привет! Как дела?") == 201
    check(f"{name}: pause", "200", call("POST", "/api/v1/agent/pause")[0] == 200)
    status, action = create_action(conv, f"match-emu-{uuid.uuid4().hex[:8]}-a")
    check(f"{name}: действие на паузе", "pending", action["status"] == "pending", action["status"])
    reject_status, rejected = call("POST", f"/api/v1/agent/actions/{action['id']}/reject")
    check(f"{name}: reject", "200", reject_status == 200, str(reject_status))
    check(f"{name}: статус", "rejected", rejected["status"] == "rejected", rejected["status"])
    check(f"{name}: resume", "200", call("POST", "/api/v1/agent/resume")[0] == 200)


def scenario_retry_no_duplicate() -> None:
    name = "7. retry_no_duplicate"
    conv = conversation()
    assert import_message(conv, "Привет! Как дела?") == 201
    key = f"match-emu-retry-live-{uuid.uuid4().hex[:6]}"
    status1, action1 = create_action(conv, key)
    status2, action2 = create_action(conv, key)
    check(f"{name}: первая отправка", "201", status1 == 201, str(status1))
    check(f"{name}: повтор ключа", "200, то же действие", status2 == 200 and action2["id"] == action1["id"], str(status2))
    actions = emulator_actions(conv, "retry-live")
    check(f"{name}: действий эмулятора в диалоге", "1", len(actions) == 1, str(len(actions)))


def scenario_autonomy_limits() -> None:
    name = "8. autonomy_limits"
    conv = conversation()
    assert import_message(conv, "Привет! Как дела?") == 201
    check(f"{name}: kill-switch", "200", set_budget(global_paused=True) == 200)
    check(f"{name}: budget", "global_paused=true", budget()["global_paused"] is True)
    status, action = create_action(conv, f"match-emu-{uuid.uuid4().hex[:8]}-a")
    check(f"{name}: действие при остановке", "pending", action["status"] == "pending", action["status"])
    approve_status, _ = call("POST", f"/api/v1/agent/actions/{action['id']}/approve")
    check(f"{name}: approve при kill-switch", "409", approve_status == 409, str(approve_status))
    check(f"{name}: снятие остановки", "200", set_budget(global_paused=False) == 200)
    approve2_status, action2 = call("POST", f"/api/v1/agent/actions/{action['id']}/approve")
    check(f"{name}: approve после снятия", "200", approve2_status == 200, str(approve2_status))
    check(f"{name}: доставлено", "sent", action2["status"] == "sent", action2["status"])


def main() -> int:
    started = time.time()
    print(f"== emulator lab live: {BASE_URL} (token: {TOKEN}) ==")
    status, health = call("GET", "/health")
    print(f"health: {status} {health}")
    if status != 200:
        print("API недоступен — прогон невозможен")
        return 2

    scenario_new_match()
    scenario_continue_with_memory()
    scenario_ambiguous()
    scenario_boundaries()
    scenario_similar_names()
    scenario_pause_cancel()
    scenario_retry_no_duplicate()
    scenario_autonomy_limits()

    failed = [row for row in results if not row[4]]
    for row in results:
        marker = "ok " if row[4] else "FAIL"
        print(f"[{marker}] {row[0]:52} | expected: {row[1]:44} | fact: {row[3]}")
    print(f"\nchecks: {len(results)}, failed: {len(failed)}, elapsed: {time.time() - started:.1f}s")
    if failed:
        print("ПРОВАЛ:", "; ".join(row[0] for row in failed))
        return 1
    print("ВСЕ ПРОВЕРКИ ЗЕЛЁНЫЕ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
