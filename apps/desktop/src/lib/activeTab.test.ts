import { test } from "node:test";
import assert from "node:assert/strict";

import { ACTIVE_TAB_KEY, loadActiveTab, saveActiveTab } from "./activeTab.ts";

// Минимальный localStorage-стаб для node (jsdom не используется в проекте).
class MemoryStorage {
  private data = new Map<string, string>();
  getItem(key: string): string | null {
    return this.data.has(key) ? (this.data.get(key) as string) : null;
  }
  setItem(key: string, value: string): void {
    this.data.set(key, String(value));
  }
  removeItem(key: string): void {
    this.data.delete(key);
  }
}

const VALID = ["profile", "matches", "memory", "settings"] as const;

function withGlobalStorage<T>(fn: () => T): T {
  const original = (globalThis as { window?: unknown }).window;
  (globalThis as { window?: unknown }).window = { localStorage: new MemoryStorage() };
  try {
    return fn();
  } finally {
    (globalThis as { window?: unknown }).window = original;
  }
}

test("loadActiveTab: fallback, когда window нет (SSR/тесты)", () => {
  const original = (globalThis as { window?: unknown }).window;
  (globalThis as { window?: unknown }).window = undefined;
  try {
    assert.equal(loadActiveTab(VALID, "profile"), "profile");
  } finally {
    (globalThis as { window?: unknown }).window = original;
  }
});

test("saveActiveTab + loadActiveTab: раунд-трип сохранения", () => {
  withGlobalStorage(() => {
    saveActiveTab("memory", VALID);
    assert.equal(loadActiveTab(VALID, "profile"), "memory");
  });
});

test("loadActiveTab: игнорирует мусорное значение", () => {
  withGlobalStorage(() => {
    window.localStorage.setItem(ACTIVE_TAB_KEY, "не-вкладка");
    assert.equal(loadActiveTab(VALID, "profile"), "profile");
  });
});

test("loadActiveTab: fallback при отсутствии записи", () => {
  withGlobalStorage(() => {
    assert.equal(loadActiveTab([], "settings"), "settings");
  });
});

test("saveActiveTab: игнорирует значение не из списка", () => {
  withGlobalStorage(() => {
    saveActiveTab("admin", VALID); // 'admin' не в VALID
    assert.equal(window.localStorage.getItem(ACTIVE_TAB_KEY), null);
  });
});
