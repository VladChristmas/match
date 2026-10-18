import { invoke } from "@tauri-apps/api/core";

import { isTauri } from "./settings";
import type { CaptureTarget, CapturedFrame } from "./types";

const UNAVAILABLE = "Захват экрана доступен только в приложении MATCH (Tauri).";

export async function listCaptureWindows(): Promise<CaptureTarget[]> {
  if (!isTauri()) throw new Error(UNAVAILABLE);
  return invoke<CaptureTarget[]>("list_capture_windows");
}

export async function captureWindowFrame(handle: number): Promise<CapturedFrame> {
  if (!isTauri()) throw new Error(UNAVAILABLE);
  return invoke<CapturedFrame>("capture_window_frame", { handle });
}

export function pngDataUrl(frame: CapturedFrame): string {
  return `data:image/png;base64,${frame.png_base64}`;
}
