import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { ApiClient } from "../lib/api";
import {
  DEFAULT_SETTINGS,
  loadSettings,
  saveSettings,
  type JournalEntry,
  type Settings,
} from "../lib/settings";
import {
  appendJournal,
  clearStoredJournal,
  JOURNAL_LIMIT,
  storageSupported,
} from "../lib/storage";
import {
  enqueueOutbox,
  flushOutbox,
  listOutbox,
  outboxSupported,
  type FlushResult,
  type OutboxRequest,
} from "../lib/outbox";

interface AppContextValue {
  ready: boolean;
  settings: Settings;
  api: ApiClient;
  update: (patch: Partial<Settings>) => void;
  logJournal: (kind: string, summary: string, detail?: string) => void;
  clearJournal: () => void;
  outboxCount: number;
  queueRequest: (request: OutboxRequest) => Promise<string>;
  syncOutbox: () => Promise<FlushResult>;
}

const OUTBOX_INTERVAL_MS = 30000;

const AppContext = createContext<AppContextValue | null>(null);

function newEntry(kind: string, summary: string, detail?: string): JournalEntry {
  return {
    id:
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    at: new Date().toISOString(),
    kind,
    summary,
    detail,
  };
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [ready, setReady] = useState(false);
  const [outboxCount, setOutboxCount] = useState(0);

  useEffect(() => {
    let active = true;
    loadSettings().then((loaded) => {
      if (!active) return;
      setSettings(loaded);
      setReady(true);
    });
    return () => {
      active = false;
    };
  }, []);

  const update = useCallback((patch: Partial<Settings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...patch };
      void saveSettings(next).catch(() => undefined);
      return next;
    });
  }, []);

  const logJournal = useCallback((kind: string, summary: string, detail?: string) => {
    const entry = newEntry(kind, summary, detail);
    setSettings((prev) => {
      const next = { ...prev, journal: [entry, ...prev.journal].slice(0, JOURNAL_LIMIT) };
      if (storageSupported()) {
        void appendJournal(entry).catch(() => undefined);
      } else {
        void saveSettings(next).catch(() => undefined);
      }
      return next;
    });
  }, []);

  const clearJournal = useCallback(() => {
    setSettings((prev) => {
      const next = { ...prev, journal: [] };
      if (storageSupported()) {
        void clearStoredJournal().catch(() => undefined);
      } else {
        void saveSettings(next).catch(() => undefined);
      }
      return next;
    });
  }, []);

  const api = useMemo(
    () => new ApiClient({ baseUrl: settings.apiBaseUrl, token: settings.token }),
    [settings.apiBaseUrl, settings.token],
  );

  const refreshOutbox = useCallback(async () => {
    if (!outboxSupported()) return;
    setOutboxCount((await listOutbox()).length);
  }, []);

  const syncOutbox = useCallback(async (): Promise<FlushResult> => {
    if (!outboxSupported()) return { sent: 0, dropped: 0, remaining: 0, reasons: [] };
    const result = await flushOutbox(api);
    await refreshOutbox();
    if (result.sent > 0) {
      logJournal("outbox", `Оффлайн-очередь синхронизирована: ${result.sent}`);
    }
    for (const reason of result.reasons) {
      logJournal("outbox", `Запрос отброшен: ${reason.label}`, reason.detail);
    }
    return result;
  }, [api, logJournal, refreshOutbox]);

  const queueRequest = useCallback(
    async (request: OutboxRequest) => {
      const id = await enqueueOutbox(request);
      await refreshOutbox();
      logJournal("outbox", `Запрос в оффлайн-очереди: ${request.label}`, id);
      return id;
    },
    [logJournal, refreshOutbox],
  );

  useEffect(() => {
    if (!ready || !outboxSupported()) return;
    void syncOutbox();
    const onOnline = () => void syncOutbox();
    window.addEventListener("online", onOnline);
    const timer = window.setInterval(() => void syncOutbox(), OUTBOX_INTERVAL_MS);
    return () => {
      window.removeEventListener("online", onOnline);
      window.clearInterval(timer);
    };
  }, [ready, syncOutbox]);

  const value = useMemo<AppContextValue>(
    () => ({
      ready,
      settings,
      api,
      update,
      logJournal,
      clearJournal,
      outboxCount,
      queueRequest,
      syncOutbox,
    }),
    [
      ready,
      settings,
      api,
      update,
      logJournal,
      clearJournal,
      outboxCount,
      queueRequest,
      syncOutbox,
    ],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
