import { invoke } from "@tauri-apps/api/core";

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
  journal: JournalEntry[];
}

export const DEFAULT_SETTINGS: Settings = {
  apiBaseUrl: "http://127.0.0.1:8000",
  token: "",
  autonomyMode: "auto_send",
  journal: [],
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
  try {
    if (isTauri()) {
      const raw = await invoke<Partial<Settings> | null>("load_settings");
      return { ...DEFAULT_SETTINGS, ...(raw ?? {}) };
    }
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return { ...DEFAULT_SETTINGS };
    return { ...DEFAULT_SETTINGS, ...(JSON.parse(raw) as Partial<Settings>) };
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

export async function saveSettings(settings: Settings): Promise<void> {
  if (isTauri()) {
    await invoke("save_settings", { settings });
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
