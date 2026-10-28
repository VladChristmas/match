/**
 * Источник кадров для лаборатории тестирования (ТЗ docs/testing/emulator-lab-spec.md §3).
 *
 * Фаза 1: симулятор Match — кадр рисуется локально в canvas.
 * Фаза 2 (задел): android-adb — `adb screencap` → PNG; сценарии переиспользуются без
 * изменений, меняется только реализация capture.
 *
 * Сценарии обращаются к FrameSource, а не к конкретному источнику — поэтому набор
 * сценариев Фазы 1 работает и на реальном Android-эмуляторе.
 */

import { captureVirtualFrame } from "./scene.ts";
import type { Orientation, Resolution, VirtualScreen } from "./screen.ts";

export interface VirtualFrame {
  png_base64: string;
  width: number;
  height: number;
}

export interface FrameSource {
  readonly kind: "simulator" | "android-adb";
  capture(
    canvas: HTMLCanvasElement,
    screen: VirtualScreen,
    options: { resolution: Resolution; orientation: Orientation; scale: number },
  ): Promise<VirtualFrame>;
}

export const simulatorFrameSource: FrameSource = {
  kind: "simulator",
  async capture(canvas, screen, options) {
    return captureVirtualFrame(canvas, screen, options);
  },
};

/**
 * Фаза 2 — НЕ реализовано. Точка расширения: `adb exec-out screencap -p` → PNG → base64.
 * canvas/screen/options аргументы игнорируются (кадр приходит с устройства).
 */
export const androidAdbFrameSource: FrameSource = {
  kind: "android-adb",
  async capture(): Promise<VirtualFrame> {
    throw new Error("android-adb frame source не реализован (Фаза 2, см. ТЗ §8.6)");
  },
};
