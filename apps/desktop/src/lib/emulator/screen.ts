/**
 * Модель виртуального экрана смартфона (Фаза 1 лаборатории тестирования).
 *
 * Чистые данные — без DOM. Сериализуемы; сценарии (Фаза 1B) оперируют этими же типами,
 * реальный Android-источник кадров (Фаза 2) переиспользует контракт, меняя только
 * способ получения кадра (см. frameSource.ts).
 */

export type ScreenMode = "matches" | "chat" | "profile" | "notification";

export type Orientation = "portrait" | "landscape";

export interface VirtualMessage {
  id: string;
  /** true — входящее (собеседник), false — исходящее (пользователь/агент). */
  inbound: boolean;
  text: string;
  at: string;
}

export interface VirtualChat {
  peerName: string;
  messages: VirtualMessage[];
  typing?: boolean;
}

export interface VirtualProfile {
  name: string;
  age: number;
  city: string;
  bio: string;
  interests: string[];
}

export interface VirtualScreen {
  mode: ScreenMode;
  statusBar: { clock: string; battery: number };
  chat?: VirtualChat;
  profile?: VirtualProfile;
  feed?: { name: string; age: number; city: string }[];
  notification?: { app: string; title: string; body: string };
}

export interface Resolution {
  id: string;
  /** Базовая ширина в портретной ориентации. */
  width: number;
  /** Базовая высота в портретной ориентации. */
  height: number;
  label: string;
}

/** Пресеты разрешений (портретные размеры; альбом — те же с обменом сторон). */
export const RESOLUTIONS: readonly Resolution[] = [
  { id: "360x640", width: 360, height: 640, label: "360×640" },
  { id: "390x844", width: 390, height: 844, label: "390×844" },
  { id: "412x915", width: 412, height: 915, label: "412×915" },
];

/** Ориентация-wise размеры кадра. Ширина кадра ≤ 1280 (MAX_FRAME_WIDTH в vision.rs). */
export function resolveDims(
  resolution: Resolution,
  orientation: Orientation,
): { width: number; height: number } {
  return orientation === "portrait"
    ? { width: resolution.width, height: resolution.height }
    : { width: resolution.height, height: resolution.width };
}

export function findResolution(id: string): Resolution {
  return RESOLUTIONS.find((item) => item.id === id) ?? RESOLUTIONS[0];
}

/** Демо-экраны для ручной проверки (Фаза 1A). Сценарии Фазы 1B строят свои. */
export const DEMO_SCREENS: Record<ScreenMode, VirtualScreen> = {
  matches: {
    mode: "matches",
    statusBar: { clock: "21:04", battery: 78 },
    feed: [
      { name: "Анна", age: 27, city: "Москва" },
      { name: "Мария", age: 25, city: "Санкт-Петербург" },
      { name: "Ольга", age: 29, city: "Казань" },
    ],
  },
  chat: {
    mode: "chat",
    statusBar: { clock: "21:07", battery: 77 },
    chat: {
      peerName: "Анна",
      typing: false,
      messages: [
        { id: "m1", inbound: false, text: "Привет! Как проходит вечер?", at: "21:01" },
        { id: "m2", inbound: true, text: "Привет! Только вернулась с прогулки)", at: "21:02" },
        { id: "m3", inbound: false, text: "Здорово. Что любишь делать на выходных?", at: "21:03" },
      ],
    },
  },
  profile: {
    mode: "profile",
    statusBar: { clock: "21:09", battery: 76 },
    profile: {
      name: "Анна",
      age: 27,
      city: "Москва",
      bio: "Люблю горные походы, кофе и тихие вечера с книгой.",
      interests: ["походы", "кофе", "книги", "фильмы"],
    },
  },
  notification: {
    mode: "notification",
    statusBar: { clock: "21:10", battery: 76 },
    notification: { app: "Знакомства", title: "Анна", body: "Новое сообщение: Привет! Как дела?" },
  },
};
