/**
 * Источник кадров для лаборатории тестирования (ТЗ docs/testing/emulator-lab-spec.md §3).
 *
 * Фаза 1: симулятор Match — кадр рисуется локально в canvas.
 * Фаза 2: android-adb — `adb exec-out screencap -p` → PNG с реального устройства
 *   (src-tauri/src/adb.rs); кадр уходит в тот же POST /api/v1/vision/observations.
 *
 * Сценарии обращаются к FrameSource, а не к конкретному источнику — поэтому набор
 * сценариев Фазы 1 работает и на реальном Android-устройстве без изменений.
 */

import { adbScreencap } from "./adb.ts";
import { captureVirtualFrame } from "./scene.ts";
import type { Orientation, Resolution, VirtualScreen } from "./screen.ts";

export interface VirtualFrame {
  png_base64: string;
  width: number;
  height: number;
}

export interface FrameSourceOptions {
  resolution: Resolution;
  orientation: Orientation;
  scale: number;
  /** Серийный номер устройства ADB (только для источника android-adb). */
  serial?: string | null;
}

export interface FrameSource {
  readonly kind: "simulator" | "android-adb";
  capture(
    canvas: HTMLCanvasElement | null,
    screen: VirtualScreen,
    options: FrameSourceOptions,
  ): Promise<VirtualFrame>;
}

export const simulatorFrameSource: FrameSource = {
  kind: "simulator",
  async capture(canvas, screen, options) {
    // resolution/orientation/scale задают сцену; serial игнорируется.
    return captureVirtualFrame(canvas, screen, options);
  },
};

/**
 * Фаза 2 — реальный Android через adb. canvas/screen/resolution игнорируются:
 * кадр приходит с устройства целиком (включая его ориентацию и разрешение).
 */
export const androidAdbFrameSource: FrameSource = {
  kind: "android-adb",
  async capture(_canvas, _screen, options) {
    // Проверка «только в Tauri» и вызов Rust-команды — внутри adbScreencap.
    const frame = await adbScreencap(options.serial ?? null);
    return { png_base64: frame.png_base64, width: frame.width, height: frame.height };
  },
};
