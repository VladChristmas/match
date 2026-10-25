import { invoke } from "@tauri-apps/api/core";

import { loadState, saveState } from "./storage";

export type AutonomyMode = "auto_send" | "suggest" | "manual" | "paused";
export interface JournalEntry {
  id: string;
  at: string;
  kind: string;
  summary: string;
  detail?: string;
}

export interface Settings {
  apiBaseUrl: string;
  token: string;
  autonomyMode: AutonomyMode;
  visionEnabled: boolean;
  visionSourceLabel: string;
  visionTargetHandle: number | null;
  journal: JournalEntry[];
  /** Стабильный локальный идентификатор пользователя для памяти в match.db. */
  localUserId: string;
}

function randomLocalUserId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export const DEFAULT_SETTINGS: Settings = {
  apiBaseUrl: "http://127.0.0.1:8000",
  token: "",
  autonomyMode: "auto_send",
  visionEnabled: false,
  visionSourceLabel: "window",
  visionTargetHandle: null,
  journal: [],
  localUserId: randomLocalUserId(),
};

const STORAGE_KEY = "match.settings.v1";

export const AUTONOMY_MODES: { id: AutonomyMode; title: string; description: string }[] = [
  {
    id: "auto_send",
    title: "Авто-отправка",
    description:
      "Агент отправляет сообщения самостоятельно в стиле пользователя. На старте это режим по умолчанию (ADR-0009).",
  },
  {
    id: "suggest",
    title: "Черновик на подтверждение",
    description:
      "Агент готовит черновик, но ничего не отправляет, пока пользователь не подтвердит.",
  },
  {
    id: "manual",
    title: "Только ручной режим",
    description: "Агент собирает контекст и подсказки, но ответы пишет пользователь.",
  },
  {
    id: "paused",
    title: "Пауза",
    description: "Агент полностью остановлен для этого диалога.",
  },
];

export function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export async function loadSettings(): Promise<Settings> {
  const snapshot = await loadState();
  let merged: Settings;
  if (snapshot) {
    merged = {
      ...DEFAULT_SETTINGS,
      ...(snapshot.settings as Partial<Settings>),
      journal: snapshot.journal as JournalEntry[],
    };
  } else {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      merged = raw
        ? { ...DEFAULT_SETTINGS, ...(JSON.parse(raw) as Partial<Settings>) }
        : { ...DEFAULT_SETTINGS };
    } catch {
      merged = { ...DEFAULT_SETTINGS };
    }
  }
  // Локальный id должен быть стабилен между запусками: сохраняем при первом появлении.
  if (!merged.localUserId) {
    merged = { ...merged, localUserId: randomLocalUserId() };
    void saveSettings(merged).catch(() => undefined);
  }
  return merged;
}

export async function saveSettings(settings: Settings): Promise<void> {
  if (isTauri()) {
    await saveState(settings);
    return;
  }
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

export interface AppInfo {
  name: string;
  version: string;
  tauri_version: string;
  os: string;
}

export async function loadAppInfo(): Promise<AppInfo | null> {
  if (!isTauri()) return null;
  try {
    return await invoke<AppInfo>("app_info");
  } catch {
    return null;
  }
}
