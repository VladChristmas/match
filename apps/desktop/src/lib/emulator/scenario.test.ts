import assert from "node:assert/strict";
import { test } from "node:test";

import { checkExpectation, describeExpectation, type Expectation, type StepOutcome } from "./expectations.ts";
import {
  idempotencyKey,
  validateScenario,
  type StepKind,
} from "./scenario.ts";
import { SCENARIOS } from "./scenarios.ts";
import type { CaptureObservationPayload, CreateActionPayload, SetBudgetPayload } from "./scenario.ts";

const EXPECTED_IDS = [
  "new_match_first_message",
  "continue_with_memory",
  "ambiguous_message",
  "boundaries_and_loss_of_interest",
  "context_loss_similar_names",
  "pause_cancel_restart",
  "retry_no_duplicate",
  "autonomy_limits",
];

test("сценарии проходят валидацию", () => {
  for (const scenario of SCENARIOS) {
    const errors = validateScenario(scenario);
    assert.deepEqual(errors, [], `${scenario.id}: ${errors.join("; ")}`);
  }
});

test("набор сценариев полон (8 обязательных из ТЗ §4)", () => {
  assert.deepEqual(
    SCENARIOS.map((item) => item.id),
    EXPECTED_IDS,
  );
  for (const scenario of SCENARIOS) {
    assert.ok(scenario.steps.length >= 3, `${scenario.id}: слишком мало шагов`);
    assert.ok(scenario.seed.length >= 1, `${scenario.id}: нет seed-диалогов`);
  }
});

test("id шагов уникальны в сценарии", () => {
  for (const scenario of SCENARIOS) {
    const ids = scenario.steps.map((step) => step.id);
    assert.equal(new Set(ids).size, ids.length, `${scenario.id}: дубли id шагов`);
  }
});

test("сценарий retry_no_duplicate: повтор с тем же ключом ожидает action_replayed", () => {
  const scenario = SCENARIOS.find((item) => item.id === "retry_no_duplicate");
  assert.ok(scenario);
  const first = scenario.steps.find((step) => step.id === "send-1");
  const retry = scenario.steps.find((step) => step.id === "send-1-retry");
  assert.ok(first && retry);
  const retryPayload = retry.payload as CreateActionPayload;
  assert.equal(retryPayload.reuse_key, "send-1");
  assert.equal(idempotencyKey("retry_no_duplicate", "send-1"), "match-emu-retry_no_duplicate-send-1");
  const predicates = retry.expect.map((item) => item.predicate);
  assert.ok(predicates.includes("http_status_is"));
  assert.ok(predicates.includes("action_replayed"));
  assert.ok(!predicates.includes("no_duplicate_action"));
});

test("сценарий autonomy_limits: kill-switch → 409 на approve", () => {
  const scenario = SCENARIOS.find((item) => item.id === "autonomy_limits");
  assert.ok(scenario);
  const stop = scenario.steps.find((step) => step.id === "stop");
  assert.ok(stop);
  assert.equal((stop.payload as SetBudgetPayload).patch.global_paused, true);
  const approve = scenario.steps.find((step) => step.id === "approve");
  assert.ok(approve);
  assert.ok(
    approve.expect.some((item) => item.predicate === "http_status_is" && item.args?.status === 409),
    "ожидание 409 не найдено",
  );
});

test("capture-шаги несут экран и source=simulator", () => {
  for (const scenario of SCENARIOS) {
    for (const step of scenario.steps) {
      if (step.kind !== "capture_observation") continue;
      const payload = step.payload as CaptureObservationPayload;
      assert.ok(payload?.screen, `${scenario.id}/${step.id}: нет экрана`);
      assert.equal(payload.source, "simulator");
    }
  }
});

function outcomeOf(overrides: StepOutcome): StepOutcome {
  return { kind: "assert_state" as StepKind, ...overrides };
}

test("checkExpectation: observation_analyzed", () => {
  const expect: Expectation = { predicate: "observation_analyzed" };
  const analyzed = outcomeOf({
    observation: { analysis_pending: false, summary: "Человек в диалоге", provider: "echo" },
  });
  const pending = outcomeOf({
    observation: { analysis_pending: true, summary: null, provider: null },
  });
  assert.equal(checkExpectation(expect, analyzed).ok, true);
  assert.equal(checkExpectation(expect, pending).ok, false);
  assert.equal(checkExpectation(expect, outcomeOf({})).ok, false);
});

test("checkExpectation: decision_mode_in", () => {
  const expect: Expectation = { predicate: "decision_mode_in", args: { modes: ["escalate", "verify"] } };
  assert.equal(checkExpectation(expect, outcomeOf({ decision: { mode: "escalate" } })).ok, true);
  assert.equal(checkExpectation(expect, outcomeOf({ decision: { mode: "execute" } })).ok, false);
  assert.match(checkExpectation(expect, outcomeOf({ decision: { mode: "execute" } })).reason, /ожидалось/);
});

test("checkExpectation: action_status_is / no_duplicate_action / action_replayed", () => {
  const status: Expectation = { predicate: "action_status_is", args: { status: "pending" } };
  const action = { id: "a", status: "pending", conversation_id: "c1" };
  const dupFree = outcomeOf({ action, duplicate: false });
  const replay = outcomeOf({ action, duplicate: true });
  assert.equal(checkExpectation(status, dupFree).ok, true);
  assert.equal(checkExpectation({ predicate: "no_duplicate_action" }, dupFree).ok, true);
  assert.equal(checkExpectation({ predicate: "no_duplicate_action" }, replay).ok, false);
  assert.equal(checkExpectation({ predicate: "action_replayed" }, replay).ok, true);
  assert.equal(checkExpectation({ predicate: "action_replayed" }, dupFree).ok, false);
});

test("checkExpectation: http_status_is / budget_field_is / action_conversation_ref", () => {
  const http: Expectation = { predicate: "http_status_is", args: { status: 409 } };
  assert.equal(checkExpectation(http, outcomeOf({ http_status: 409 })).ok, true);
  assert.equal(checkExpectation(http, outcomeOf({ http_status: 201 })).ok, false);
  const budget: Expectation = { predicate: "budget_field_is", args: { field: "global_paused", value: true } };
  assert.equal(checkExpectation(budget, outcomeOf({ budget: { global_paused: true } })).ok, true);
  assert.equal(checkExpectation(budget, outcomeOf({ budget: { global_paused: false } })).ok, false);
  const ref: Expectation = { predicate: "action_conversation_ref", args: { conversation_ref: "anna-1" } };
  assert.equal(checkExpectation(ref, outcomeOf({ action: { id: "a", status: "sent", conversation_id: "anna-1" } })).ok, true);
  assert.equal(checkExpectation(ref, outcomeOf({ action: { id: "a", status: "sent", conversation_id: "anna-2" } })).ok, false);
});

test("checkExpectation: неизвестный предикат не зелёный", () => {
  const result = checkExpectation(
    { predicate: "whatever" } as unknown as Expectation,
    outcomeOf({}),
  );
  assert.equal(result.ok, false);
});

test("describeExpectation: человекочитаемые описания для всех предикатов набора", () => {
  for (const scenario of SCENARIOS) {
    for (const step of scenario.steps) {
      for (const expect of step.expect) {
        const text = describeExpectation(expect);
        assert.ok(!text.includes("неизвестное"), `${scenario.id}/${step.id}: ${text}`);
        assert.ok(text.length > 5);
      }
    }
  }
});
