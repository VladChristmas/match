import { test } from "node:test";
import assert from "node:assert/strict";

import { summarizeLLMStatus } from "./llmStatus.ts";
import type { LLMStatus } from "./types.ts";

function makeStatus(overrides: Partial<LLMStatus> = {}): LLMStatus {
  return {
    provider: "echo",
    fallback_providers: [],
    declared_providers: ["echo"],
    skipped_providers: [],
    user_request_limit: 0,
    user_request_limit_enabled: false,
    timeout_seconds: 30,
    ...overrides,
  };
}

test("echo по умолчанию — предупреждение (офлайн-заглушка)", () => {
  const summary = summarizeLLMStatus(makeStatus());
  assert.equal(summary.tone, "warn");
  assert.ok(summary.warnings.some((w) => w.includes("echo")));
  assert.match(summary.headline, /Модель: echo/);
  assert.match(summary.limitText, /Лимит запросов не ограничен/);
});

test("реальный провайдер с лимитом — без предупреждений", () => {
  const summary = summarizeLLMStatus(
    makeStatus({
      provider: "openai",
      fallback_providers: ["echo"],
      declared_providers: ["openai", "echo"],
      user_request_limit: 100,
      user_request_limit_enabled: true,
    }),
  );
  assert.equal(summary.tone, "ok");
  assert.deepEqual(summary.warnings, []);
  assert.ok(summary.headline.includes("fallback: echo"));
  assert.match(summary.limitText, /Лимит: 100/);
});

test("пропущенные провайдеры — предупреждение с фактической цепочкой", () => {
  const summary = summarizeLLMStatus(
    makeStatus({
      provider: "echo",
      fallback_providers: [],
      declared_providers: ["openai", "echo"],
      skipped_providers: ["openai"],
      user_request_limit: 50,
      user_request_limit_enabled: true,
    }),
  );
  assert.equal(summary.tone, "warn");
  assert.ok(summary.warnings.some((w) => w.includes("openai") && w.includes("ключа")));
});

test("лимит выключен (0) — предупреждение", () => {
  const summary = summarizeLLMStatus(makeStatus({ provider: "ollama" }));
  assert.ok(summary.warnings.some((w) => w.includes("Лимит запросов на пользователя выключен")));
});
