/**
 * Отрисовка виртуального смартфона (Фаза 1A лаборатории).
 *
 * Ключевое разделение (по ТЗ docs/testing/emulator-lab-spec.md §3):
 * - buildScene — ЧИСТАЯ функция: экран + опции → список операндов отрисовки.
 *   Покрывается node-тестами (координаты конечны, команды непусты для всех режимов).
 * - paint / captureVirtualFrame — тонкая DOM-обвязка (canvas), тестами не покрывается.
 *
 * Кадр рисуется локально в canvas (НЕ захват окна приложения): кадр телефона не должен
 * содержать интерфейс лаборатории, и это работает в dev-браузере без Tauri.
 */

import type { Orientation, Resolution, VirtualScreen } from "./screen.ts";
import { resolveDims } from "./screen.ts";

export type DrawCommand =
  | { op: "clear"; color: string }
  | { op: "rect"; x: number; y: number; w: number; h: number; color: string }
  | { op: "roundRect"; x: number; y: number; w: number; h: number; r: number; color: string }
  | {
      op: "text";
      x: number;
      y: number;
      text: string;
      size: number;
      color: string;
      weight?: "normal" | "bold";
      align?: "left" | "center" | "right";
    };

export interface SceneOptions {
  resolution: Resolution;
  orientation: Orientation;
}

export interface Scene {
  width: number;
  height: number;
  commands: DrawCommand[];
}

const FONT_STACK = "system-ui, sans-serif";
const COLORS = {
  bezel: "#1b1e24",
  screen: "#101319",
  surface: "#1c2230",
  surfaceAlt: "#242c3d",
  text: "#e8ecf3",
  textMuted: "#9aa4b5",
  accent: "#3f7dfb",
  inbound: "#2a3346",
  outbound: "#3f7dfb",
};

/** Перенос текста по числу символов (без метрик шрифта — детерминизм важнее точности). */
export function wrapText(text: string, maxChars: number): string[] {
  const words = text.split(/\s+/).filter((word) => word.length > 0);
  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (candidate.length <= maxChars) {
      current = candidate;
      continue;
    }
    if (current) lines.push(current);
    current = word;
  }
  if (current) lines.push(current);
  return lines.length > 0 ? lines : [""];
}

function chatScene(
  screen: VirtualScreen,
  commands: DrawCommand[],
  width: number,
  top: number,
  offsetX: number,
): void {
  const chat = screen.chat;
  if (!chat) return;
  const pad = 10;
  const headerH = 40;
  commands.push({
    op: "rect",
    x: 0,
    y: top,
    w: width,
    h: headerH,
    color: COLORS.surfaceAlt,
  });
  commands.push({
    op: "text",
    x: pad + 4,
    y: top + 26,
    text: chat.peerName,
    size: 15,
    color: COLORS.text,
    weight: "bold",
  });

  let y = top + headerH + 14;
  const bubbleMax = Math.max(40, width - pad * 2 - 80);
  const maxChars = Math.max(8, Math.floor(bubbleMax / 7));
  for (const message of chat.messages) {
    const lines = wrapText(message.text, maxChars);
    const bubbleW = Math.min(bubbleMax, Math.max(...lines.map((line) => line.length)) * 7 + 18);
    const bubbleH = lines.length * 18 + 14;
    const x = message.inbound ? offsetX + pad : offsetX + width - pad - bubbleW;
    commands.push({
      op: "roundRect",
      x,
      y,
      w: bubbleW,
      h: bubbleH,
      r: 10,
      color: message.inbound ? COLORS.inbound : COLORS.outbound,
    });
    lines.forEach((line, index) => {
      commands.push({
        op: "text",
        x: x + 9,
        y: y + 20 + index * 18,
        text: line,
        size: 13,
        color: COLORS.text,
      });
    });
    y += bubbleH + 8;
  }
  if (chat.typing) {
    commands.push({
      op: "text",
      x: offsetX + pad + 6,
      y: y + 16,
      text: "…печатает",
      size: 12,
      color: COLORS.textMuted,
    });
  }
}

/** Чистая сборка сцены: экран + опции → операнды отрисовки. */
export function buildScene(screen: VirtualScreen, options: SceneOptions): Scene {
  const { width, height } = resolveDims(options.resolution, options.orientation);
  const commands: DrawCommand[] = [];
  const bezel = 10;

  commands.push({ op: "clear", color: COLORS.bezel });
  commands.push({
    op: "roundRect",
    x: bezel,
    y: bezel,
    w: width - bezel * 2,
    h: height - bezel * 2,
    r: 24,
    color: COLORS.screen,
  });

  const innerX = bezel + 4;
  const innerW = width - (bezel + 4) * 2;
  const top = bezel + 4;

  // Статус-бар: часы слева, батарея справа (детерминированные значения из сценария).
  commands.push({
    op: "text",
    x: innerX + 12,
    y: top + 18,
    text: screen.statusBar.clock,
    size: 12,
    color: COLORS.text,
  });
  commands.push({
    op: "text",
    x: innerX + innerW - 12,
    y: top + 18,
    text: `${Math.round(screen.statusBar.battery)}%`,
    size: 12,
    color: COLORS.textMuted,
    align: "right",
  });

  const contentTop = top + 30;

  if (screen.mode === "chat") {
    chatScene(screen, commands, innerW, contentTop, innerX);
  } else if (screen.mode === "matches") {
    const feed = screen.feed ?? [];
    commands.push({
      op: "text",
      x: innerX + 12,
      y: contentTop + 22,
      text: "Знакомства",
      size: 16,
      color: COLORS.text,
      weight: "bold",
    });
    let y = contentTop + 36;
    for (const person of feed) {
      commands.push({
        op: "roundRect",
        x: innerX + 10,
        y,
        w: innerW - 20,
        h: 58,
        r: 12,
        color: COLORS.surface,
      });
      commands.push({
        op: "text",
        x: innerX + 22,
        y: y + 24,
        text: person.name,
        size: 14,
        color: COLORS.text,
        weight: "bold",
      });
      commands.push({
        op: "text",
        x: innerX + 22,
        y: y + 42,
        text: `${person.age}, ${person.city}`,
        size: 12,
        color: COLORS.textMuted,
      });
      y += 66;
    }
  } else if (screen.mode === "profile") {
    const profile = screen.profile;
    if (profile) {
      commands.push({
        op: "text",
        x: innerX + 12,
        y: contentTop + 22,
        text: `${profile.name}, ${profile.age}`,
        size: 16,
        color: COLORS.text,
        weight: "bold",
      });
      commands.push({
        op: "text",
        x: innerX + 12,
        y: contentTop + 44,
        text: profile.city,
        size: 13,
        color: COLORS.accent,
      });
      let y = contentTop + 62;
      for (const line of wrapText(profile.bio, Math.floor((innerW - 24) / 7))) {
        commands.push({ op: "text", x: innerX + 12, y, text: line, size: 13, color: COLORS.text });
        y += 18;
      }
      let x = innerX + 12;
      for (const interest of profile.interests) {
        const w = interest.length * 7 + 16;
        commands.push({
          op: "roundRect",
          x,
          y,
          w,
          h: 24,
          r: 12,
          color: COLORS.surfaceAlt,
        });
        commands.push({ op: "text", x: x + 8, y: y + 16, text: interest, size: 12, color: COLORS.text });
        x += w + 8;
      }
    }
  } else if (screen.mode === "notification") {
    const note = screen.notification;
    if (note) {
      commands.push({
        op: "roundRect",
        x: innerX + 10,
        y: contentTop + 10,
        w: innerW - 20,
        h: 76,
        r: 14,
        color: COLORS.surface,
      });
      commands.push({
        op: "text",
        x: innerX + 24,
        y: contentTop + 34,
        text: note.app,
        size: 11,
        color: COLORS.accent,
      });
      commands.push({
        op: "text",
        x: innerX + 24,
        y: contentTop + 52,
        text: note.title,
        size: 13,
        color: COLORS.text,
        weight: "bold",
      });
      commands.push({
        op: "text",
        x: innerX + 24,
        y: contentTop + 70,
        text: note.body,
        size: 12,
        color: COLORS.textMuted,
      });
    }
  }

  return { width, height, commands };
}

/** Тонкая DOM-обвязка: выполняет операнды на canvas с учётом масштаба отображения. */
export function paint(ctx: CanvasRenderingContext2D, scene: Scene, scale: number): void {
  ctx.setTransform(scale, 0, 0, scale, 0, 0);
  ctx.font = FONT_STACK;
  for (const command of scene.commands) {
    ctx.fillStyle = command.color;
    if (command.op === "clear") {
      ctx.fillRect(0, 0, scene.width, scene.height);
    } else if (command.op === "rect") {
      ctx.fillRect(command.x, command.y, command.w, command.h);
    } else if (command.op === "roundRect" && typeof ctx.roundRect === "function") {
      ctx.beginPath();
      ctx.roundRect(command.x, command.y, command.w, command.h, command.r);
      ctx.fill();
    } else if (command.op === "roundRect") {
      ctx.fillRect(command.x, command.y, command.w, command.h);
    } else {
      ctx.font = `${command.weight === "bold" ? "bold " : ""}${command.size}px ${FONT_STACK}`;
      ctx.textAlign = command.align ?? "left";
      ctx.textBaseline = "alphabetic";
      ctx.fillText(command.text, command.x, command.y);
    }
  }
  ctx.setTransform(1, 0, 0, 1, 0, 0);
}

/** Кадр из canvas: paint сцены → PNG base64 (без data-префикса — как ждёт decode_png_frame). */
export function captureVirtualFrame(
  canvas: HTMLCanvasElement,
  screen: VirtualScreen,
  options: SceneOptions & { scale: number },
): { png_base64: string; width: number; height: number } {
  const { scale, ...sceneOptions } = options;
  const scene = buildScene(screen, sceneOptions);
  canvas.width = scene.width;
  canvas.height = scene.height;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("canvas 2d context unavailable");
  paint(ctx, scene, scale);
  const dataUrl = canvas.toDataURL("image/png");
  const png_base64 = dataUrl.slice(dataUrl.indexOf(",") + 1);
  return { png_base64, width: scene.width, height: scene.height };
}
