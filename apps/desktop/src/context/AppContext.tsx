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

interface AppContextValue {
  ready: boolean;
  settings: Settings;
  api: ApiClient;
  update: (patch: Partial<Settings>) => void;
  logJournal: (kind: string, summary: string, detail?: string) => void;
  clearJournal: () => void;
}

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
    setSettings((prev) => {
      const next = { ...prev, journal: [newEntry(kind, summary, detail), ...prev.journal].slice(0, 500) };
      void saveSettings(next).catch(() => undefined);
      return next;
    });
  }, []);

  const clearJournal = useCallback(() => {
    setSettings((prev) => {
      const next = { ...prev, journal: [] };
      void saveSettings(next).catch(() => undefined);
      return next;
    });
  }, []);

  const api = useMemo(
    () => new ApiClient({ baseUrl: settings.apiBaseUrl, token: settings.token }),
    [settings.apiBaseUrl, settings.token],
  );

  const value = useMemo<AppContextValue>(
    () => ({ ready, settings, api, update, logJournal, clearJournal }),
    [ready, settings, api, update, logJournal, clearJournal],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
