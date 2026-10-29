import assert from "node:assert/strict";
import { test } from "node:test";

import type { FrameSource } from "./frameSource.ts";
import { createScenarioRunner, type RunnerApi } from "./runner.ts";
import { SCENARIOS } from "./scenarios.ts";
import type { Scenario } from "./scenario.ts";
import type { ActionFact, DecisionFact, ObservationFact } from "./expectations.ts";

const FRAME = { png_base64: "AAAA", width: 360, height: 640 };

function scenarioById(id: string): Scenario {
  const scenario = SCENARIOS.find((item) => item.id === id);
  assert.ok(scenario, `нет сценария ${id}`);
  return scenario;
}

interface FakeState {
  actions: ActionFact[];
  budget: Record<string, unknown>;
  observations: { conversation_id: string; analyze: boolean; source_label?: string }[];
  idSeq: number;
  keys: Map<string, ActionFact>;
}

class HttpLikeError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/**
 * Фейк повторяет РЕАЛЬНУЮ семантику бэкенда, проверенную по коду:
 * enqueue_action при заблокированном бюджете → PENDING (service.py:157–169);
 * approve при kill-switch → 409 «Delivery blocked by autonomy budget» (agent.py:146–161);
 * повтор Idempotency-Key → 200 + то же действие.
 */
function fakeApi(
  state: FakeState,
  deferredImport?: { promise: Promise<void> },
): RunnerApi {
  return {
    async createConversation() {
      state.idSeq += 1;
      return { id: `conv-${state.idSeq}` };
    },
    async importMessage() {
      if (deferredImport) await deferredImport.promise;
      return {};
    },
    async createVisionObservation(payload) {
      state.observations.push({
        conversation_id: payload.conversation_id,
        analyze: payload.analyze,
        source_label: payload.source_label,
      });
      const observation: ObservationFact = {
        analysis_pending: false,
        summary: "экран диалога знакомств",
        provider: "echo",
      };
      return observation;
    },
    async evaluateDecision(): Promise<DecisionFact> {
      return { mode: "execute", escalation_reason: null };
    },
    async createActionWithStatus(payload, key) {
      const existing = key ? state.keys.get(key) : undefined;
      if (existing) return { status: 200, action: existing };
      state.idSeq += 1;
      const action: ActionFact = {
        id: `action-${state.idSeq}`,
        status: state.budget.global_paused ? "pending" : "sent",
        conversation_id: payload.conversation_id,
        idempotency_key: key ?? null,
      };
      state.actions.push(action);
      if (key) state.keys.set(key, action);
      return { status: 201, action };
    },
    async approveAction(id) {
      if (state.budget.global_paused === true) {
        throw new HttpLikeError(409, "Delivery blocked by autonomy budget: global_paused");
      }
      const action = state.actions.find((item) => item.id === id);
      if (action) action.status = "sent";
      return action!;
    },
    async rejectAction(id) {
      const action = state.actions.find((item) => item.id === id);
      if (action) action.status = "rejected";
      return action!;
    },
    async pauseAgent() {
      return {};
    },
    async resumeAgent() {
      return {};
    },
    async listActions() {
      return [...state.actions];
    },
    async getAutonomyBudget() {
      return { ...state.budget };
    },
    async updateAutonomyBudget(payload) {
      state.budget = { ...state.budget, ...payload };
      return { ...state.budget };
    },
  };
}

function fakeFrameSource(): FrameSource {
  return {
    kind: "simulator",
    async capture() {
      return FRAME;
    },
  };
}

function freshState(): FakeState {
  return {
    actions: [],
    budget: { global_paused: false, max_messages_per_day: 50 },
    observations: [],
    idSeq: 0,
    keys: new Map(),
  };
}

function makeRunner(state: FakeState, deferredImport?: { promise: Promise<void> }) {
  return createScenarioRunner({
    api: fakeApi(state, deferredImport),
    getCanvas: () => null,
    frameSource: fakeFrameSource(),
  });
}

test("прогон new_match_first_message: все шаги ok, наблюдение реальное", async () => {
  const state = freshState();
  const runner = makeRunner(state);
  await runner.run(scenarioById("new_match_first_message"));
  const snapshot = runner.getSnapshot();
  assert.equal(snapshot.status, "done");
  assert.ok(snapshot.results.every((item) => item.ok), JSON.stringify(snapshot.results, null, 1));
  assert.equal(state.observations.length, 1);
  assert.equal(state.observations[0].analyze, true);
  assert.equal(state.observations[0].source_label, "emulator");
});

test("retry_no_duplicate: повтор ключа = 200, в диалоге ровно одно действие", async () => {
  const state = freshState();
  const runner = makeRunner(state);
  await runner.run(scenarioById("retry_no_duplicate"));
  const snapshot = runner.getSnapshot();
  assert.equal(snapshot.status, "done");
  assert.ok(snapshot.results.every((item) => item.ok), JSON.stringify(snapshot.results, null, 1));
  assert.equal(state.actions.length, 1);
  const retryStep = snapshot.results.find((item) => item.step_id === "send-1-retry");
  assert.equal(retryStep?.http_status, 200);
  assert.equal(retryStep?.duplicate, true);
});

test("autonomy_limits: kill-switch → pending, approve 409, снятие → sent", async () => {
  const state = freshState();
  const runner = makeRunner(state);
  await runner.run(scenarioById("autonomy_limits"));
  const snapshot = runner.getSnapshot();
  assert.equal(snapshot.status, "done");
  assert.ok(snapshot.results.every((item) => item.ok), JSON.stringify(snapshot.results, null, 1));
  const actStep = snapshot.results.find((item) => item.step_id === "act");
  assert.equal(actStep?.action?.status, "pending");
  const approveStep = snapshot.results.find((item) => item.step_id === "approve");
  assert.equal(approveStep?.http_status, 409);
  const approve2 = snapshot.results.find((item) => item.step_id === "approve-2");
  assert.equal(approve2?.http_status, 200);
  assert.equal(approve2?.action?.status, "sent");
});

test("pause/resume: шаги не выполняются на паузе", async () => {
  const state = freshState();
  let resolveImport!: () => void;
  const deferredImport = { promise: new Promise<void>((r) => (resolveImport = r)) };
  const runner = makeRunner(state, deferredImport);
  const running = runner.run(scenarioById("new_match_first_message"));
  await new Promise((r) => setTimeout(r, 20));
  runner.pause();
  assert.equal(runner.getSnapshot().status, "paused");
  resolveImport();
  await new Promise((r) => setTimeout(r, 50));
  assert.equal(runner.getSnapshot().results.length, 0, "шаги не должны идти на паузе");
  runner.resume();
  await running;
  assert.equal(runner.getSnapshot().status, "done");
  assert.ok(runner.getSnapshot().results.length > 0);
});

test("reset: прогон обрывается, статус idle", async () => {
  const state = freshState();
  let resolveImport!: () => void;
  const deferredImport = { promise: new Promise<void>((r) => (resolveImport = r)) };
  const runner = makeRunner(state, deferredImport);
  const running = runner.run(scenarioById("new_match_first_message"));
  await new Promise((r) => setTimeout(r, 20));
  runner.reset();
  resolveImport();
  await running;
  assert.equal(runner.getSnapshot().status, "idle");
});

test("невалидный сценарий → failed, сеть не трогается", async () => {
  const state = freshState();
  const runner = makeRunner(state);
  const broken = scenarioById("retry_no_duplicate");
  broken.steps[0].conversation_ref = "нет-такого";
  await runner.run(broken);
  assert.equal(runner.getSnapshot().status, "failed");
  assert.match(runner.getSnapshot().runError ?? "", /неизвестная метка диалога/);
  assert.equal(state.actions.length, 0);
});
