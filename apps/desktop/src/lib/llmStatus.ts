import type { LLMStatus } from "./types";

export type LLMStatusTone = "ok" | "warn" | "error";

export interface LLMStatusSummary {
  /** Заголовок: кто фактически получает промпты. */
  headline: string;
  tone: LLMStatusTone;
  /** Расхождения между настройками и реальным поведением. */
  warnings: string[];
  /** Расходный лимит на пользователя. */
  limitText: string;
}

/** echo — офлайн-заглушка, а не генерация: считаем это предупреждением (аудит P1-1). */
const OFFLINE_PROVIDER = "echo";

/**
 * Человекочитаемое описание статуса LLM из `/api/v1/llm/status`.
 * Чистая функция — покрывается node-тестом (`llmStatus.test.ts`).
 */
export function summarizeLLMStatus(status: LLMStatus): LLMStatusSummary {
  const warnings: string[] = [];

  if (status.provider === OFFLINE_PROVIDER) {
    warnings.push(
      "Провайдер echo — офлайн-заглушка (эхо входящего текста), не генерация. Задайте провайдера в настройках сервера.",
    );
  }
  if (status.skipped_providers.length > 0) {
    warnings.push(
      `Пропущены за неналичием ключа/настройки: ${status.skipped_providers.join(", ")} — фактическая цепочка: ${[
        status.provider,
        ...status.fallback_providers,
      ].join(" → ")}.`,
    );
  }
  if (!status.user_request_limit_enabled) {
    warnings.push("Лимит запросов на пользователя выключен (0 = неограниченный расход).");
  }

  const chain = [status.provider, ...status.fallback_providers].filter(Boolean);
  return {
    headline: `Модель: ${status.provider}${chain.length > 1 ? ` (fallback: ${status.fallback_providers.join(", ")})` : ""}`,
    tone: warnings.length === 0 ? "ok" : status.provider === OFFLINE_PROVIDER ? "warn" : "warn",
    warnings,
    limitText: status.user_request_limit_enabled
      ? `Лимит: ${status.user_request_limit} запросов на пользователя (0 = без лимита)`
      : "Лимит запросов не ограничен",
  };
}
