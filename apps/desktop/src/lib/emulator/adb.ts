/**
 * ADB-источник кадров и жестов (Фаза 2 лаборатории «Эмулятор и тесты», ТЗ §8.6).
 *
 * Кадр снимается с реального устройства Android (`adb exec-out screencap -p`) и уходит
 * в тот же POST /api/v1/vision/observations (analyze=true) — сценарии Фазы 1
 * переиспользуются без изменений, меняется только источник кадра.
 *
 * Жесты (тап/свайп/назад) — реальные `adb shell input` по пикселям кадра.
 * Тонкая TS-обвязка над Rust-командами (src-tauri/src/adb.rs); единственная
 * чистая функция здесь — pointToDevice (покрыта node-тестом).
 */

import { invoke } from "@tauri-apps/api/core";

import type { CapturedFrame } from "../types.ts";

const UNAVAILABLE =
  "ADB-источник доступен только в приложении MATCH (Tauri): adb запускается из Rust-слоя.";

/**
 * Детект Tauri продублирован здесь сознательно (а не импорт из settings.ts):
 * settings.ts тянет storage.rs-обвязку, а node-тесты лаборатории импортируют
 * frameSource → adb.ts и должны оставаться чистыми (паттерн llmStatus.ts).
 */
function isTauri(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

export interface AdbDevice {
  serial: string;
  /** device | unauthorized | offline | bootloader — состояние из `adb devices -l`. */
  state: string;
  model: string | null;
}

export interface DevicePoint {
  x: number;
  y: number;
}

/**
 * Точка превью (client px внутри отображаемого прямоугольника) → пиксели экрана устройства.
 * Чистая функция: координаты клипа, размеры кадра известны — маппинг детерминирован.
 */
export function pointToDevice(
  clientX: number,
  clientY: number,
  rect: { left: number; top: number; width: number; height: number },
  frameWidth: number,
  frameHeight: number,
): DevicePoint {
  if (rect.width <= 0 || rect.height <= 0) return { x: 0, y: 0 };
  const ratioX = (clientX - rect.left) / rect.width;
  const ratioY = (clientY - rect.top) / rect.height;
  return {
    x: clampToFrame(ratioX * frameWidth, frameWidth),
    y: clampToFrame(ratioY * frameHeight, frameHeight),
  };
}

function clampToFrame(value: number, frameSize: number): number {
  const max = Math.max(0, frameSize - 1);
  if (!Number.isFinite(value)) return 0;
  return Math.max(0, Math.min(Math.floor(value), max));
}

export async function listAdbDevices(): Promise<AdbDevice[]> {
  if (!isTauri()) throw new Error(UNAVAILABLE);
  return invoke<AdbDevice[]>("adb_devices");
}

export async function adbScreencap(serial: string | null): Promise<CapturedFrame> {
  if (!isTauri()) throw new Error(UNAVAILABLE);
  return invoke<CapturedFrame>("adb_screencap", { serial });
}

export async function adbTap(serial: string | null, x: number, y: number): Promise<void> {
  if (!isTauri()) throw new Error(UNAVAILABLE);
  await invoke("adb_tap", { serial, x, y });
}

export async function adbSwipe(
  serial: string | null,
  x1: number,
  y1: number,
  x2: number,
  y2: number,
  durationMs: number,
): Promise<void> {
  if (!isTauri()) throw new Error(UNAVAILABLE);
  await invoke("adb_swipe", { serial, x1, y1, x2, y2, durationMs });
}

export async function adbBack(serial: string | null): Promise<void> {
  if (!isTauri()) throw new Error(UNAVAILABLE);
  await invoke("adb_key", { serial, keycode: 4 });
}
