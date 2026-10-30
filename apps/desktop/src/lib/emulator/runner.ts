/**
 * Движок прогона сценариев лаборатории (ТЗ docs/testing/emulator-lab-spec.md §4).
 *
 * Жёсткое правило ТЗ: сценарий выполняется через РЕАЛЬНЫЕ endpoint'ы MATCH
 * (vision-наблюдения, решения, действия, бюджет). Симулятор не имитирует агента —
 * он лишь подаёт кадры и записывает факты.
 *
 * Тестируемость: зависимости (api, frameSource, canvas) инъецируются — node-тесты
 * гоняют сценарии на фейках без сети (runner.test.ts).
 */

import {
  checkExpectation,
  describeExpectation,
  type StepOutcome,
} from "./expectations.ts";
import type { FrameSource } from "./frameSource.ts";
import { simulatorFrameSource } from "./frameSource.ts";
import {
  RESOLUTIONS,
  findResolution,
  type Orientation,
  type VirtualScreen,
} from "./screen.ts";
import {
  idempotencyKey,
  validateScenario,
  type BudgetPatch,
  type CreateActionPayload,
  type DecisionActionPayload,
  type EvaluateDecisionPayload,
  type ImportMessagePayload,
  type CaptureObservationPayload,
  type Scenario,
  type ScenarioStep,
  type SetBudgetPayload,
  type StepResult,
} from "./scenario.ts";
import type { ActionFact, DecisionFact, ObservationFact } from "./expectations.ts";
import type { AgentAction, AutonomyBudget } from "../types.ts";

export type RunnerStatus = "idle" | "running" | "paused" | "done" | "failed";

/** API-надмножество для раннера (ApiClient структурно удовлетворяет). */
export interface RunnerApi {
  createConversation(payload: { autonomy_mode?: string }): Promise<{ id: string }>;
  importMessage(
    id: string,
    payload: { content: string; direction: "inbound" | "outbound"; source?: string },
  ): Promise<unknown>;
  createVisionObservation(payload: {
    conversation_id: string;
    frame_base64: string;
    source_label?: string;
    captured_at?: string | null;
    analyze: boolean;
  }): Promise<ObservationFact>;
  evaluateDecision(payload: {
    conversation_id: string;
    trigger_text?: string | null;
  }): Promise<DecisionFact>;
  createActionWithStatus(
    payload: { conversation_id: string; text?: string | null; generate?: boolean },
    idempotencyKey?: string,
  ): Promise<{ status: number; action: ActionFact }>;
  approveAction(id: string): Promise<ActionFact>;
  rejectAction(id: string): Promise<ActionFact>;
  pauseAgent(): Promise<unknown>;
  resumeAgent(): Promise<unknown>;
  listActions(status?: string, limit?: number): Promise<AgentAction[]>;
  getAutonomyBudget(): Promise<AutonomyBudget>;
  updateAutonomyBudget(payload: BudgetPatch): Promise<AutonomyBudget>;
}

export interface RenderOptions {
  resolutionId: string;
  orientation: Orientation;
  scale: number;
}

export interface RunnerOptions {
  api: RunnerApi;
  frameSource?: FrameSource;
  getCanvas: () => HTMLCanvasElement | null;
  renderOptions?: RenderOptions;
  /** Живые настройки рендера (UI может менять разрешение на ходу прогона). */
  getRenderOptions?: () => RenderOptions;
  onStatus?: (status: RunnerStatus) => void;
  onResult?: (result: StepResult) => void;
}

export interface RunnerSnapshot {
  status: RunnerStatus;
  results: readonly StepResult[];
  scenarioId: string | null;
  runError: string | null;
}

export interface ScenarioRunner {
  run(scenario: Scenario): Promise<void>;
  pause(): void;
  resume(): void;
  reset(): void;
  subscribe(listener: () => void): () => void;
  getSnapshot(): RunnerSnapshot;
}

class ApiHttpError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiHttpError";
    this.status = status;
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function createScenarioRunner(options: RunnerOptions): ScenarioRunner {
  const {
    api,
    frameSource = simulatorFrameSource,
    getCanvas,
    renderOptions = { resolutionId: RESOLUTIONS[0].id, orientation: "portrait", scale: 1 },
    getRenderOptions,
    onStatus,
    onResult,
  } = options;

  let status: RunnerStatus = "idle";
  let results: StepResult[] = [];
  let scenarioId: string | null = null;
  let runError: string | null = null;
  let paused = false;
  let resetRequested = false;
  const listeners = new Set<() => void>();
  let snapshot: RunnerSnapshot = { status, results, scenarioId, runError };

  function emit(): void {
    snapshot = { status, results: [...results], scenarioId, runError };
    for (const listener of listeners) listener();
    onStatus?.(status);
  }

  function setStatus(next: RunnerStatus): void {
    status = next;
    emit();
  }

  /** Кооперативные пауза/сброс между шагами. */
  async function gate(): Promise<void> {
    while (paused && !resetRequested) {
      await sleep(100);
    }
  }

  function statusOfError(err: unknown): number | undefined {
    if (err instanceof ApiHttpError) return err.status;
    if (err && typeof err === "object" && "status" in err) {
      const value = (err as { status: unknown }).status;
      if (typeof value === "number") return value;
    }
    return undefined;
  }

  function pushResult(result: StepResult): void {
    results.push(result);
    onResult?.(result);
    emit();
  }

  /** Память фактов для assert_state: ожидания проверяются против последних известных фактов. */
  const memory: {
    action: ActionFact | null;
    duplicate: boolean;
    budget: Record<string, unknown> | null;
  } = { action: null, duplicate: false, budget: null };

  async function runStep(
    scenario: Scenario,
    step: ScenarioStep,
    conversations: Map<string, string>,
  ): Promise<StepResult> {
    const started = Date.now();
    const outcome: StepOutcome = { kind: step.kind };
    const conversationId = conversations.get(step.conversation_ref) ?? "";
    const expected = step.expect.map(describeExpectation).join("; ") || "—";
    const actualParts: string[] = [];
    let httpStatus: number | undefined;

    try {
      switch (step.kind) {
        case "show_screen": {
          // Только рендер; кадра не создаём — сценарии capture_observation делают это явно.
          break;
        }
        case "capture_observation": {
          const payload = step.payload as CaptureObservationPayload;
          const canvas = getCanvas();
          const screen: VirtualScreen = payload.screen;
          const live = getRenderOptions ? getRenderOptions() : renderOptions;
          const resolution = findResolution(live.resolutionId);
          const frame = await frameSource.capture(canvas, screen, {
            resolution,
            orientation: live.orientation,
            scale: live.scale,
          });
          const observation = await api.createVisionObservation({
            conversation_id: conversationId,
            frame_base64: frame.png_base64,
            source_label: "emulator",
            captured_at: new Date().toISOString(),
            analyze: true,
          });
          httpStatus = 201;
          outcome.observation = observation;
          actualParts.push(
            `${frame.width}×${frame.height}, ${observation.analysis_pending ? "analysis_pending" : "analyzed"}`,
          );
          break;
        }
        case "import_message": {
          const payload = step.payload as ImportMessagePayload;
          await api.importMessage(conversationId, {
            content: payload.text,
            direction: payload.direction,
            source: "emulator",
          });
          httpStatus = 201;
          actualParts.push(`сообщение импортировано (${payload.direction})`);
          break;
        }
        case "evaluate_decision": {
          const payload = step.payload as EvaluateDecisionPayload;
          const decision = await api.evaluateDecision({
            conversation_id: conversationId,
            trigger_text: payload.text ?? null,
          });
          httpStatus = 200;
          outcome.decision = decision;
          actualParts.push(`решение: ${decision.mode}`);
          break;
        }
        case "create_action": {
          const payload = step.payload as CreateActionPayload;
          const key = idempotencyKey(
            scenario.id,
            payload.reuse_key ? `${payload.reuse_key}` : step.id,
          );
          const usedBefore = usedKeys.has(key);
          const created = await api.createActionWithStatus(
            {
              conversation_id: conversationId,
              text: payload.text ?? null,
              generate: payload.generate ?? false,
            },
            key,
          );
          httpStatus = created.status;
          outcome.http_status = created.status;
          outcome.action = created.action;
          outcome.duplicate = usedBefore && created.status === 200 && created.action !== null;
          usedKeys.add(key);
          lastActionId = created.action?.id ?? null;
          actualParts.push(`действие ${created.action?.status ?? "?"} (HTTP ${created.status})`);
          break;
        }
        case "approve_action":
        case "reject_action": {
          const payload = step.payload as DecisionActionPayload;
          const actionId =
            payload.action_ref === "last"
              ? lastActionId
              : actionIdsByStep.get(payload.action_ref) ?? null;
          if (!actionId) throw new ApiHttpError(0, "нет действия для решения");
          const action =
            step.kind === "approve_action"
              ? await api.approveAction(actionId)
              : await api.rejectAction(actionId);
          httpStatus = 200;
          outcome.action = action;
          memory.action = action;
          actualParts.push(`${step.kind}: ${action.status}`);
          break;
        }
        case "agent_pause": {
          await api.pauseAgent();
          httpStatus = 200;
          actualParts.push("агент на паузе");
          break;
        }
        case "agent_resume": {
          await api.resumeAgent();
          httpStatus = 200;
          actualParts.push("агент возобновлён");
          break;
        }
        case "set_budget": {
          const payload = step.payload as SetBudgetPayload;
          const patch: BudgetPatch = payload.patch;
          const budget = await api.updateAutonomyBudget({ ...patch });
          httpStatus = 200;
          memory.budget = budget as unknown as Record<string, unknown>;
          outcome.budget = memory.budget;
          actualParts.push(`бюджет обновлён: ${Object.keys(patch).join(", ")}`);
          break;
        }
        case "wait_outbox_flush": {
          await sleep(1500);
          actualParts.push("ожидание синхронизации");
          break;
        }
        case "assert_state": {
          // Факты берём из памяти прогона: бюджет/действие/дубль последних шагов.
          // Для action_count_is — реальный подсчёт действий эмулятора в диалоге.
          const countExpects = step.expect.filter((item) => item.predicate === "action_count_is");
          if (countExpects.length > 0) {
            const actions = await api.listActions(undefined, 200);
            outcome.emulator_action_count = actions.filter(
              (item) =>
                item.conversation_id === conversationId &&
                (item.idempotency_key ?? "").startsWith(`match-emu-${scenario.id}-`),
            ).length;
          }
          outcome.budget =
            memory.budget ?? ((await api.getAutonomyBudget()) as unknown as Record<string, unknown>);
          if (!memory.budget) memory.budget = outcome.budget;
          outcome.action = memory.action;
          outcome.duplicate = memory.duplicate;
          break;
        }
      }
    } catch (err) {
      httpStatus = httpStatus ?? statusOfError(err);
      outcome.http_status = httpStatus;
      const message = err instanceof Error ? err.message : String(err);
      // Факты прошлых шагов остаются валидными: ожидание action_status_is на упавшем
      // approve проверяется против последнего известного действия.
      outcome.action = outcome.action ?? memory.action;
      outcome.duplicate = outcome.duplicate ?? memory.duplicate;
      outcome.budget = outcome.budget ?? memory.budget;
      const checks = step.expect.map((expect) => ({ expect, check: checkExpectation(expect, outcome) }));
      const ok = checks.every((item) => item.check.ok);
      const result: StepResult = {
        step_id: step.id,
        title: step.title,
        ok,
        http_status: httpStatus,
        expected,
        actual: checks.map((item) => item.check.actual).join("; ") || message,
        duration_ms: Date.now() - started,
        error: message,
      };
      return result;
    }

    outcome.http_status = httpStatus;
    const checks = step.expect.map((expect) => {
      const resolved =
        expect.predicate === "action_conversation_ref"
          ? {
              ...expect,
              args: { ...expect.args, conversation_ref: conversationId || String(expect.args?.conversation_ref) },
            }
          : expect;
      return { expect: resolved, check: checkExpectation(resolved, outcome) };
    });
    const ok = checks.length === 0 ? true : checks.every((item) => item.check.ok);
    if (outcome.action) {
      memory.action = { ...outcome.action };
      if (step.kind === "create_action") actionIdsByStep.set(step.id, outcome.action.id);
    }
    memory.duplicate = outcome.duplicate ?? memory.duplicate;

    return {
      step_id: step.id,
      title: step.title,
      ok,
      http_status: httpStatus,
      expected,
      actual: actualParts.join("; ") || checks.map((item) => item.check.actual).join("; ") || "—",
      duration_ms: Date.now() - started,
      observation: outcome.observation ?? undefined,
      action: outcome.action ? { id: outcome.action.id, status: outcome.action.status } : undefined,
      duplicate: outcome.duplicate,
    };
  }

  const usedKeys = new Set<string>();
  const actionIdsByStep = new Map<string, string>();
  let lastActionId: string | null = null;

  async function seed(scenario: Scenario): Promise<Map<string, string>> {
    const conversations = new Map<string, string>();
    for (const item of scenario.seed) {
      const conversation = await api.createConversation(
        item.autonomy_mode ? { autonomy_mode: item.autonomy_mode } : {},
      );
      conversations.set(item.label, conversation.id);
      for (const message of item.messages ?? []) {
        await api.importMessage(conversation.id, {
          content: message.text,
          direction: message.direction,
          source: "emulator-seed",
        });
      }
    }
    return conversations;
  }

  async function run(scenario: Scenario): Promise<void> {
    resetRequested = false;
    paused = false;
    usedKeys.clear();
    actionIdsByStep.clear();
    lastActionId = null;
    memory.action = null;
    memory.duplicate = false;
    memory.budget = null;
    scenarioId = scenario.id;
    setStatus("running");

    const errors = validateScenario(scenario);
    if (errors.length > 0) {
      runError = errors.join("; ");
      setStatus("failed");
      return;
    }
    runError = null;

    try {
      const conversations = await seed(scenario);
      for (const step of scenario.steps) {
        await gate();
        if (resetRequested) {
          setStatus("idle");
          return;
        }
        const result = await runStep(scenario, step, conversations);
        pushResult(result);
      }
      setStatus("done");
    } catch (err) {
      if (resetRequested) {
        setStatus("idle");
        return;
      }
      runError = err instanceof Error ? err.message : String(err);
      setStatus("failed");
    }
  }

  return {
    async run(scenario) {
      await run(scenario);
    },
    pause() {
      if (status !== "running") return;
      paused = true;
      setStatus("paused");
    },
    resume() {
      if (status !== "paused") return;
      paused = false;
      setStatus("running");
    },
    reset() {
      resetRequested = true;
      paused = false;
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    getSnapshot() {
      return snapshot;
    },
  };
}
