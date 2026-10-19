import { invoke } from "@tauri-apps/api/core";
import type {
  LocalConversation,
  LocalMessage,
  Memory,
  MemoryCreate,
  MemoryEvent,
  MemoryKind,
  MemoryStatus,
  MemoryUpdate,
} from "./types";

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
  memory_entries: number;
  local_profile_entries: number;
  local_conversations_entries: number;
  local_messages_entries: number;
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

export async function addMemory(
  userId: string,
  payload: MemoryCreate,
): Promise<Memory> {
  if (!storageSupported()) throw new Error("local storage unsupported");
  const now = new Date().toISOString();
  const entry: Memory = {
    id: crypto.randomUUID(),
    user_id: userId,
    conversation_id: payload.conversation_id ?? null,
    kind: payload.kind,
    status: "received",
    content: payload.content,
    source: payload.source ?? "message",
    confidence: payload.confidence ?? 0.5,
    valid_until: payload.valid_until ?? null,
    created_at: now,
    updated_at: now,
  };
  await invoke<void>("memory_add", { entry });
  return entry;
}

export async function listMemory(
  userId: string,
  {
    conversation_id,
    kind,
    status,
    limit = 50,
    offset = 0,
  }: {
    conversation_id?: string | null;
    kind?: MemoryKind | null;
    status?: MemoryStatus | null;
    limit?: number;
    offset?: number;
  } = {},
): Promise<Memory[]> {
  if (!storageSupported()) return [];
  return await invoke<Memory[]>("memory_list", {
    user_id: userId,
    conversation_id: conversation_id ?? null,
    kind: kind ?? null,
    status: status ?? null,
    limit,
    offset,
  });
}

export async function getMemory(userId: string, id: string): Promise<Memory | null> {
  if (!storageSupported()) return null;
  try {
    return await invoke<Memory>("memory_get", { id, user_id: userId });
  } catch {
    return null;
  }
}

export async function classifyMemory(
  userId: string,
  id: string,
  kind: MemoryKind,
): Promise<Memory | null> {
  if (!storageSupported()) return null;
  const now = new Date().toISOString();
  try {
    return await invoke<Memory>("memory_classify", {
      id,
      user_id: userId,
      kind,
      updated_at: now,
      event_created_at: now,
    });
  } catch {
    return null;
  }
}

export async function verifyMemory(
  userId: string,
  id: string,
): Promise<Memory | null> {
  if (!storageSupported()) return null;
  const now = new Date().toISOString();
  try {
    return await invoke<Memory>("memory_verify", {
      id,
      user_id: userId,
      updated_at: now,
      event_created_at: now,
    });
  } catch {
    return null;
  }
}

export async function correctMemory(
  userId: string,
  id: string,
  { content, confidence }: MemoryUpdate,
): Promise<Memory | null> {
  if (!storageSupported()) return null;
  const now = new Date().toISOString();
  try {
    return await invoke<Memory>("memory_correct", {
      id,
      user_id: userId,
      content: content ?? null,
      confidence: confidence ?? null,
      updated_at: now,
      event_created_at: now,
    });
  } catch {
    return null;
  }
}

export async function deleteMemory(userId: string, id: string): Promise<boolean> {
  if (!storageSupported()) return false;
  try {
    return await invoke<boolean>("memory_delete", { id, user_id: userId });
  } catch {
    return false;
  }
}

export async function memoryEvents(memoryId: string): Promise<MemoryEvent[]> {
  if (!storageSupported()) return [];
  try {
    return await invoke<MemoryEvent[]>("memory_events", { memory_id: memoryId });
  } catch {
    return [];
  }
}

export async function profileSave(
  userId: string,
  kind: "profile" | "communication",
  profileJson: string,
  updatedAt: string,
): Promise<void> {
  if (!storageSupported()) return;
  await invoke<void>("profile_save", { user_id: userId, kind, profile_json: profileJson, updated_at: updatedAt });
}

export async function profileLoad(
  userId: string,
  kind: "profile" | "communication",
): Promise<string | null> {
  if (!storageSupported()) return null;
  try {
    return await invoke<string>("profile_load", { user_id: userId, kind });
  } catch {
    return null;
  }
}

export async function conversationsSave(entries: LocalConversation[]): Promise<void> {
  if (!storageSupported()) return;
  await invoke<void>("conversations_save", { entries });
}

export async function conversationsLoad(userId: string): Promise<LocalConversation[]> {
  if (!storageSupported()) return [];
  try {
    return await invoke<LocalConversation[]>("conversations_load", { user_id: userId });
  } catch {
    return [];
  }
}

export async function messagesSave(entries: LocalMessage[]): Promise<void> {
  if (!storageSupported()) return;
  await invoke<void>("messages_save", { entries });
}

export async function messagesLoad(conversationId: string): Promise<LocalMessage[]> {
  if (!storageSupported()) return [];
  try {
    return await invoke<LocalMessage[]>("messages_load", { conversation_id: conversationId });
  } catch {
    return [];
  }
}
