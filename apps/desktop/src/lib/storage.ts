import { invoke } from "@tauri-apps/api/core";

export interface StoredJournalEntry {
  id: string;
  at: string;
  kind: string;
  summary: string;
  detail?: string;
}

export interface StateSnapshot {
  settings: Record<string, unknown>;
  journal: StoredJournalEntry[];
}

export interface StorageInfo {
  path: string;
  schema_version: number;
  sqlite_version: string;
  journal_entries: number;
  outbox_entries: number;
  size_bytes: number;
  settings_present: boolean;
}

export const JOURNAL_LIMIT = 500;

export function storageSupported(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export async function loadState(): Promise<StateSnapshot | null> {
  if (!storageSupported()) return null;
  try {
    const snapshot = await invoke<StateSnapshot>("load_state");
    return { settings: snapshot.settings ?? {}, journal: snapshot.journal ?? [] };
  } catch {
    return null;
  }
}

export async function saveState(settings: unknown): Promise<void> {
  if (!storageSupported()) return;
  await invoke("save_state", { settings });
}

export async function appendJournal(entry: StoredJournalEntry): Promise<void> {
  if (!storageSupported()) return;
  await invoke("journal_append", { entry });
}

export async function clearStoredJournal(): Promise<void> {
  if (!storageSupported()) return;
  await invoke("journal_clear");
}

export async function loadStorageInfo(): Promise<StorageInfo | null> {
  if (!storageSupported()) return null;
  try {
    return await invoke<StorageInfo>("storage_info");
  } catch {
    return null;
  }
}
