import { invoke } from "@tauri-apps/api/core";

import { ApiError, errorMessage, type ApiClient } from "./api";
import { storageSupported } from "./storage";

export interface OutboxItem {
  id: string;
  at: string;
  method: string;
  path: string;
  body?: string;
  idempotency_key?: string;
  label: string;
  attempts: number;
  last_error?: string;
}

export interface OutboxRequest {
  method: string;
  path: string;
  body?: string;
  idempotencyKey?: string;
  label: string;
}

export interface FlushResult {
  sent: number;
  dropped: number;
  remaining: number;
}

export function outboxSupported(): boolean {
  return storageSupported();
}

function newId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export async function enqueueOutbox(request: OutboxRequest): Promise<string> {
  if (!outboxSupported()) return "";
  const item: OutboxItem = {
    id: newId(),
    at: new Date().toISOString(),
    method: request.method,
    path: request.path,
    body: request.body,
    idempotency_key: request.idempotencyKey,
    label: request.label,
    attempts: 0,
  };
  await invoke("outbox_add", { entry: item });
  return item.id;
}

export async function listOutbox(): Promise<OutboxItem[]> {
  if (!outboxSupported()) return [];
  try {
    return await invoke<OutboxItem[]>("outbox_list");
  } catch {
    return [];
  }
}

export async function removeOutbox(id: string): Promise<void> {
  if (!outboxSupported()) return;
  await invoke("outbox_remove", { id });
}

export async function failOutbox(id: string, error: string): Promise<void> {
  if (!outboxSupported()) return;
  await invoke("outbox_fail", { id, error });
}

export async function clearOutbox(): Promise<void> {
  if (!outboxSupported()) return;
  await invoke("outbox_clear");
}

/**
 * Повторяет запросы очереди. Успешные и «необратимые» (4xx) удаляются,
 * сетевые/серверные (5xx, status 0) остаются с увеличенным счётчиком попыток.
 */
export async function flushOutbox(api: ApiClient): Promise<FlushResult> {
  const result: FlushResult = { sent: 0, dropped: 0, remaining: 0 };
  const items = await listOutbox();
  for (const item of items) {
    try {
      await api.send(item.path, {
        method: item.method,
        body: item.body,
        idempotencyKey: item.idempotency_key,
      });
      await removeOutbox(item.id);
      result.sent += 1;
    } catch (error) {
      if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
        await removeOutbox(item.id);
        result.dropped += 1;
      } else {
        await failOutbox(item.id, errorMessage(error));
        result.remaining += 1;
      }
    }
  }
  return result;
}
