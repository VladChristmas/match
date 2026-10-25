export const ACTIVE_TAB_KEY = "match.activeTab";

/** Допустимые идентификаторы вкладок (экспортировано из App как единственный источник истины). */
export type TabId = string;

function isBrowserStorage(): boolean {
  return typeof window !== "undefined" && "localStorage" in window;
}

/**
 * Читает сохранённую вкладку из localStorage.
 * Возвращает fallback при: отсутствии storage (SSR/тесты), пустом/битом значению,
 * значении не из списка допустимых вкладок.
 */
export function loadActiveTab<T extends TabId>(valid: readonly T[], fallback: T): T {
  if (!isBrowserStorage()) return fallback;
  let stored: string | null = null;
  try {
    stored = window.localStorage.getItem(ACTIVE_TAB_KEY);
  } catch {
    return fallback;
  }
  if (stored === null) return fallback;
  return (valid as readonly string[]).includes(stored) ? (stored as T) : fallback;
}

/** Сохраняет активную вкладку. Ошибки storage (приватный режим, квота) не должны ломать UI. */
export function saveActiveTab<T extends TabId>(id: T, valid: readonly T[]): void {
  if (!isBrowserStorage()) return;
  if (!valid.includes(id)) return;
  try {
    window.localStorage.setItem(ACTIVE_TAB_KEY, id);
  } catch {
    /* storage недоступен — молча игнорируем */
  }
}
