/**
 * Сценарии лаборатории — ДАННЫЕ, а не хардкод (ТЗ docs/testing/emulator-lab-spec.md §4).
 *
 * Сценарий ссылается на диалоги по метке seed (label), а не по UUID: раннер Фазы 1C
 * создаёт диалоги через существующие endpoint'ы и подставляет фактические id.
 * Детерминированный Idempotency-Key `match-emu-{scenario}-{step}` обеспечивает
 * проверку «retry без дубля» при повторном прогоне.
 */

import { EXPECTATION_PREDICATES, type Expectation } from "./expectations.ts";
import type { VirtualScreen } from "./screen.ts";

export type StepKind =
  | "show_screen"
  | "capture_observation"
  | "import_message"
  | "evaluate_decision"
  | "create_action"
  | "approve_action"
  | "reject_action"
  | "wait_outbox_flush"
  | "assert_state"
  | "agent_pause"
  | "agent_resume"
  | "set_budget";

export const STEP_KINDS: readonly StepKind[] = [
  "show_screen",
  "capture_observation",
  "import_message",
  "evaluate_decision",
  "create_action",
  "approve_action",
  "reject_action",
  "wait_outbox_flush",
  "assert_state",
  "agent_pause",
  "agent_resume",
  "set_budget",
];

export type ExpectationStepKind =
  | "capture_observation"
  | "import_message"
  | "evaluate_decision"
  | "create_action"
  | "assert_state"
  | "agent_pause"
  | "agent_resume"
  | "set_budget";

/** Какие ожидания осмысленны для какого шага (проверяется валидатором). */
export const KIND_EXPECTATIONS: Record<StepKind, readonly string[]> = {
  show_screen: [],
  capture_observation: ["observation_analyzed", "observation_pending", "http_status_is"],
  import_message: ["http_status_is"],
  evaluate_decision: ["decision_mode_in", "http_status_is"],
  create_action: [
    "action_status_is",
    "no_duplicate_action",
    "action_replayed",
    "http_status_is",
    "action_conversation_ref",
    "decision_mode_in",
  ],
  approve_action: ["http_status_is", "action_status_is", "decision_mode_in"],
  reject_action: ["http_status_is", "action_status_is"],
  wait_outbox_flush: [],
  assert_state: [
    "action_status_is",
    "no_duplicate_action",
    "action_count_is",
    "budget_field_is",
    "http_status_is",
    "decision_mode_in",
  ],
  agent_pause: ["http_status_is"],
  agent_resume: ["http_status_is"],
  set_budget: ["http_status_is", "budget_field_is"],
};

export type BudgetPatch = Record<string, string | number | boolean>;

export interface ShowScreenPayload {
  screen: VirtualScreen;
}

export interface CaptureObservationPayload {
  screen: VirtualScreen;
  source?: "simulator" | "android-adb";
}

export interface ImportMessagePayload {
  text: string;
  direction: "inbound" | "outbound";
}

export interface EvaluateDecisionPayload {
  /** Тригер решения. Пусто → решение строится на состоянии диалога (как CI-тест). */
  text?: string;
}

export interface CreateActionPayload {
  text?: string;
  generate?: boolean;
  schedule_in_seconds?: number;
  /** Повторно использовать ключ идемпотентности другого шага (сценарий «retry без дубля»). */
  reuse_key?: string;
}

/** Ссылка на действие: последнее созданное в сценарии или конкретный шаг. */
export interface DecisionActionPayload {
  action_ref: "last" | string;
}

export interface WaitOutboxPayload {
  timeout_ms?: number;
}

export interface SetBudgetPayload {
  patch: BudgetPatch;
}

export type StepPayload =
  | ShowScreenPayload
  | CaptureObservationPayload
  | ImportMessagePayload
  | EvaluateDecisionPayload
  | CreateActionPayload
  | DecisionActionPayload
  | WaitOutboxPayload
  | SetBudgetPayload
  | Record<string, never>;

export interface ScenarioStep {
  id: string;
  kind: StepKind;
  title: string;
  /** Метка seed-диалога (label), к которому относится шаг. */
  conversation_ref: string;
  payload?: StepPayload;
  expect: Expectation[];
}

export interface SeedMessage {
  text: string;
  direction: "inbound" | "outbound";
}

export interface SeedConversation {
  label: string;
  autonomy_mode?: string;
  messages?: SeedMessage[];
}

export interface Scenario {
  id: string;
  title: string;
  seed: SeedConversation[];
  steps: ScenarioStep[];
}

/** Результат шага для UI (ТЗ §4). */
export interface StepResult {
  step_id: string;
  title: string;
  ok: boolean;
  http_status?: number;
  expected: string;
  actual: string;
  duration_ms: number;
  error?: string;
  observation?: { analysis_pending: boolean; summary: string | null; provider: string | null } | null;
  action?: { id: string; status: string } | null;
  duplicate?: boolean;
}

/** Детерминированный ключ идемпотентности шага. */
export function idempotencyKey(scenarioId: string, stepId: string): string {
  return `match-emu-${scenarioId}-${stepId}`;
}

/** Валидация сценария: используется раннером перед прогоном и node-тестами. */
export function validateScenario(scenario: Scenario): string[] {
  const errors: string[] = [];
  const labels = new Set<string>();
  for (const seed of scenario.seed) {
    if (!seed.label) errors.push("seed: пустая метка диалога");
    if (labels.has(seed.label)) errors.push(`seed: дублирующаяся метка ${seed.label}`);
    labels.add(seed.label);
  }
  const stepIds = new Set<string>();
  for (const step of scenario.steps) {
    if (!step.id) errors.push("шаг без id");
    if (stepIds.has(step.id)) errors.push(`дублирующийся id шага: ${step.id}`);
    stepIds.add(step.id);
    if (!labels.has(step.conversation_ref)) {
      errors.push(`шаг ${step.id}: неизвестная метка диалога ${step.conversation_ref}`);
    }
    if (step.kind === "show_screen" || step.kind === "wait_outbox_flush") {
      if (step.expect.length > 0) errors.push(`шаг ${step.id}: ${step.kind} не несёт ожиданий`);
    } else if (step.expect.length === 0) {
      errors.push(`шаг ${step.id}: нет ожиданий`);
    }
    for (const expect of step.expect) {
      if (!EXPECTATION_PREDICATES.includes(expect.predicate)) {
        errors.push(`шаг ${step.id}: неизвестный предикат ${String(expect.predicate)}`);
        continue;
      }
      if (!KIND_EXPECTATIONS[step.kind].includes(expect.predicate)) {
        errors.push(`шаг ${step.id}: предикат ${expect.predicate} неприменим к ${step.kind}`);
      }
    }
    if (step.kind === "capture_observation") {
      const payload = step.payload as CaptureObservationPayload | undefined;
      if (!payload?.screen) errors.push(`шаг ${step.id}: нет экрана для кадра`);
    }
    if (step.kind === "import_message") {
      const payload = step.payload as ImportMessagePayload | undefined;
      if (!payload?.text) errors.push(`шаг ${step.id}: нет текста сообщения`);
    }
    if (step.kind === "evaluate_decision") {
      const payload = step.payload as EvaluateDecisionPayload | undefined;
      // text опционален: без тригера decide() работает по состоянию диалога
      // (reciprocity/неоднозначность) — так устроен CI-тест test_safety_autonomous.
      if (payload !== undefined && payload.text !== undefined && payload.text.length === 0) {
        errors.push(`шаг ${step.id}: пустой триггерный текст`);
      }
    }
    if (step.kind === "create_action") {
      const payload = step.payload as CreateActionPayload | undefined;
      if (!payload || (payload.text === undefined && payload.generate !== true)) {
        errors.push(`шаг ${step.id}: create_action без text и без generate`);
      }
    }
    if (step.kind === "set_budget") {
      const payload = step.payload as SetBudgetPayload | undefined;
      if (!payload?.patch || Object.keys(payload.patch).length === 0) {
        errors.push(`шаг ${step.id}: пустой patch бюджета`);
      }
    }
  }
  return errors;
}
