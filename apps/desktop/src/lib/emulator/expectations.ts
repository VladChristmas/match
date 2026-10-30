/**
 * Ожидания шага сценария (ТЗ docs/testing/emulator-lab-spec.md §4).
 *
 * Чистый модуль: `checkExpectation(expect, outcome)` без сети/DOM — покрывается
 * node-тестами. Ожидания проверяют ПОВЕДЕНИЕ (mode, статус, HTTP-код, дубли),
 * а не текст summary: вывод Vision зависит от провайдера и недетерминирован.
 */

import type { StepKind } from "./scenario.ts";

export type ExpectationPredicate =
  | "observation_analyzed"
  | "observation_pending"
  | "decision_mode_in"
  | "action_status_is"
  | "no_duplicate_action"
  | "action_replayed"
  | "action_count_is"
  | "http_status_is"
  | "budget_field_is"
  | "action_conversation_ref";

export const EXPECTATION_PREDICATES: readonly ExpectationPredicate[] = [
  "observation_analyzed",
  "observation_pending",
  "decision_mode_in",
  "action_status_is",
  "no_duplicate_action",
  "action_replayed",
  "action_count_is",
  "http_status_is",
  "budget_field_is",
  "action_conversation_ref",
];

export type ExpectationArg = string | number | boolean | string[];

export interface Expectation {
  predicate: ExpectationPredicate;
  args?: Record<string, ExpectationArg>;
}

export interface ObservationFact {
  analysis_pending: boolean;
  summary: string | null;
  provider: string | null;
}

export interface DecisionFact {
  mode: string;
  escalation_reason?: string | null;
  stop_reason?: string | null;
}

export interface ActionFact {
  id: string;
  status: string;
  conversation_id: string;
  idempotency_key: string | null;
}

/** Фактический результат шага — то, с чем сравниваются ожидания. */
export interface StepOutcome {
  kind: StepKind;
  http_status?: number;
  observation?: ObservationFact | null;
  decision?: DecisionFact | null;
  action?: ActionFact | null;
  /** true — ответ на create_action с этим Idempotency-Key вернулся как повтор (200). */
  duplicate?: boolean;
  budget?: Record<string, unknown> | null;
  /** Число действий эмулятора (idempotency_key начинается с match-emu-) в диалоге. */
  emulator_action_count?: number;
}

export interface ExpectationResult {
  ok: boolean;
  /** Человекочитаемый факт («как получилось»). */
  actual: string;
  /** Причина провала или подтверждение. */
  reason: string;
}

function argString(args: Record<string, ExpectationArg> | undefined, key: string): string | null {
  const value = args?.[key];
  return typeof value === "string" ? value : null;
}

function argNumber(args: Record<string, ExpectationArg> | undefined, key: string): number | null {
  const value = args?.[key];
  return typeof value === "number" ? value : null;
}

function argStringArray(
  args: Record<string, ExpectationArg> | undefined,
  key: string,
): string[] | null {
  const value = args?.[key];
  if (Array.isArray(value) && value.every((item) => typeof item === "string")) {
    return value as string[];
  }
  return null;
}

/** Человекочитаемое описание ожидания (колонка «ожидаемый результат» в UI). */
export function describeExpectation(expect: Expectation): string {
  switch (expect.predicate) {
    case "observation_analyzed":
      return "наблюдение проанализировано провайдером (summary заполнен)";
    case "observation_pending":
      return "наблюдение осталось analysis_pending (провайдер недоступен/троттлинг)";
    case "decision_mode_in":
      return `решение агента — одно из [${(expect.args?.modes as string[] | undefined)?.join(", ") ?? "?"}]`;
    case "action_status_is":
      return `действие в статусе ${argString(expect.args, "status") ?? "?"}`;
    case "no_duplicate_action":
      return "первое создание: дубля по Idempotency-Key нет";
    case "action_replayed":
      return "повтор с тем же Idempotency-Key вернул то же действие (без создания нового)";
    case "action_count_is":
      return `действий эмулятора в диалоге ровно ${String(expect.args?.count)}`;
    case "http_status_is":
      return `HTTP-статус ${argNumber(expect.args, "status") ?? "?"}`;
    case "budget_field_is":
      return `бюджет: ${argString(expect.args, "field") ?? "?"} = ${String(expect.args?.value)}`;
    case "action_conversation_ref":
      return `действие привязано к диалогу ${argString(expect.args, "conversation_ref") ?? "?"}`;
    default:
      return "неизвестное ожидание";
  }
}

/** Сверка ожидания с фактом. */
export function checkExpectation(expect: Expectation, outcome: StepOutcome): ExpectationResult {
  switch (expect.predicate) {
    case "observation_analyzed": {
      const observation = outcome.observation ?? null;
      if (!observation) return { ok: false, actual: "наблюдения нет", reason: "шаг не создал наблюдение" };
      if (observation.analysis_pending) {
        return {
          ok: false,
          actual: "analysis_pending=true",
          reason: "провайдер не ответил (недоступен/троттлинг/лимит)",
        };
      }
      return {
        ok: Boolean(observation.summary),
        actual: observation.summary ? "summary заполнен" : "summary пуст",
        reason: observation.summary ? "анализ выполнен" : "анализ без текста",
      };
    }
    case "observation_pending": {
      const observation = outcome.observation ?? null;
      if (!observation) return { ok: false, actual: "наблюдения нет", reason: "шаг не создал наблюдение" };
      return {
        ok: observation.analysis_pending,
        actual: `analysis_pending=${observation.analysis_pending}`,
        reason: observation.analysis_pending ? "ожидаемо не проанализировано" : "анализ выполнен — ожидалось иначе",
      };
    }
    case "decision_mode_in": {
      const modes = argStringArray(expect.args, "modes");
      const decision = outcome.decision ?? null;
      if (!decision) return { ok: false, actual: "решения нет", reason: "шаг не вернул решение" };
      if (!modes) return { ok: false, actual: decision.mode, reason: "ожидание без списка modes" };
      return {
        ok: modes.includes(decision.mode),
        actual: decision.mode,
        reason: modes.includes(decision.mode) ? "решение в разрешённом наборе" : `ожидалось одно из [${modes.join(", ")}]`,
      };
    }
    case "action_status_is": {
      const expected = argString(expect.args, "status");
      const action = outcome.action ?? null;
      if (!action) return { ok: false, actual: "действия нет", reason: "шаг не создал действия" };
      if (!expected) return { ok: false, actual: action.status, reason: "ожидание без status" };
      return {
        ok: action.status === expected,
        actual: action.status,
        reason: action.status === expected ? "статус совпал" : `ожидался ${expected}`,
      };
    }
    case "no_duplicate_action": {
      const action = outcome.action ?? null;
      if (!action) return { ok: false, actual: "действия нет", reason: "шаг не создал действия" };
      const duplicate = outcome.duplicate === true;
      return {
        ok: !duplicate,
        actual: duplicate ? "повернулось существующее действие (дубль-запрос)" : "одно действие",
        reason: duplicate ? "дубликат допущен" : "дубля нет",
      };
    }
    case "action_replayed": {
      const action = outcome.action ?? null;
      if (!action) return { ok: false, actual: "действия нет", reason: "шаг не создал действия" };
      const replayed = outcome.duplicate === true;
      return {
        ok: replayed,
        actual: replayed ? `повтор вернул действие ${action.id.slice(0, 8)}…` : "создано новое действие",
        reason: replayed ? "idempotency сработала" : "повторный ключ не распознан",
      };
    }
    case "action_count_is": {
      const expected = argNumber(expect.args, "count");
      const count = outcome.emulator_action_count;
      if (count === undefined) {
        return { ok: false, actual: "счётчик действий недоступен", reason: "раннер не подсчитал действия" };
      }
      if (expected === undefined) return { ok: false, actual: String(count), reason: "ожидание без count" };
      return {
        ok: count === expected,
        actual: String(count),
        reason: count === expected ? "дублей нет" : `ожидалось ${expected}`,
      };
    }
    case "http_status_is": {
      const expected = argNumber(expect.args, "status");
      const status = outcome.http_status;
      if (status === undefined) return { ok: false, actual: "HTTP-вызова не было", reason: "шаг без HTTP" };
      if (expected === undefined) return { ok: false, actual: String(status), reason: "ожидание без status" };
      return {
        ok: status === expected,
        actual: String(status),
        reason: status === expected ? "статус совпал" : `ожидался ${expected}`,
      };
    }
    case "budget_field_is": {
      const field = argString(expect.args, "field");
      const budget = outcome.budget ?? null;
      if (!budget || !field) return { ok: false, actual: "бюджета нет", reason: "снимок бюджета недоступен" };
      const value = budget[field];
      const expectedValue = expect.args?.value;
      return {
        ok: value === expectedValue,
        actual: `${field}=${String(value)}`,
        reason: value === expectedValue ? "поле совпало" : `ожидалось ${String(expectedValue)}`,
      };
    }
    case "action_conversation_ref": {
      // args.conversation_ref в сценарии — метка seed; раннер подставляет UUID диалога.
      const expected = argString(expect.args, "conversation_ref");
      const action = outcome.action ?? null;
      if (!action) return { ok: false, actual: "действия нет", reason: "шаг не создал действия" };
      if (!expected) return { ok: false, actual: action.conversation_id, reason: "ожидание без conversation_ref" };
      return {
        ok: action.conversation_id === expected,
        actual: action.conversation_id,
        reason:
          action.conversation_id === expected
            ? "привязка к верному диалогу"
            : "действие привязано к другому диалогу",
      };
    }
    default:
      return { ok: false, actual: "—", reason: `неизвестный предикат ${String(expect.predicate)}` };
  }
}
