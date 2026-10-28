import { useState } from "react";

import { AppProvider, useApp } from "./context/AppContext";
import { AdminView } from "./views/AdminView";
import { EmulatorView } from "./views/EmulatorView";
import { AnalysisView } from "./views/AnalysisView";
import { AutonomyView } from "./views/AutonomyView";
import { Banner, Button } from "./components/ui";
import { DecisionsView } from "./views/DecisionsView";
import { DynamicsView } from "./views/DynamicsView";
import { JournalView } from "./views/JournalView";
import { MatchesView } from "./views/MatchesView";
import { MemoryView } from "./views/MemoryView";
import { PrivacyView } from "./views/PrivacyView";
import { ProfileView } from "./views/ProfileView";
import { SettingsView } from "./views/SettingsView";
import { VisionView } from "./views/VisionView";
import { loadActiveTab, saveActiveTab } from "./lib/activeTab";
import "./styles.css";

type Tab =
  | "profile"
  | "matches"
  | "analysis"
  | "autonomy"
  | "decisions"
  | "dynamics"
  | "memory"
  | "vision"
  | "journal"
  | "emulator"
  | "admin"
  | "privacy"
  | "settings";

const TABS: { id: Tab; label: string }[] = [
  { id: "profile", label: "Профиль" },
  { id: "matches", label: "Знакомства" },
  { id: "analysis", label: "Анализ" },
  { id: "autonomy", label: "Автономность" },
  { id: "decisions", label: "Решения" },
  { id: "dynamics", label: "Динамика" },
  { id: "memory", label: "Память" },
  { id: "vision", label: "Зрение" },
  { id: "journal", label: "Журнал" },
  { id: "emulator", label: "Эмулятор и тесты" },
  { id: "admin", label: "Админ" },
  { id: "privacy", label: "Приватность" },
  { id: "settings", label: "Настройки" },
];

const TAB_IDS: readonly Tab[] = TABS.map((item) => item.id);

function Shell() {
  const { ready, settings } = useApp();
  const [tab, setTab] = useState<Tab>(() => loadActiveTab(TAB_IDS, "profile"));

  const selectTab = (id: Tab) => {
    setTab(id);
    saveActiveTab(id, TAB_IDS);
  };

  if (!ready) {
    return <div className="boot">Загрузка MATCH…</div>;
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">M</span>
          <div className="brand-text">
            <strong>MATCH</strong>
            <span className="muted">ассистент знакомств</span>
          </div>
        </div>
        <nav className="nav">
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`nav-item ${tab === item.id ? "active" : ""}`}
              onClick={() => selectTab(item.id)}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <span className="muted">API</span>
          <code>{settings.apiBaseUrl || "не задан"}</code>
          <span className="muted">{settings.token ? "токен задан" : "токен не задан"}</span>
        </div>
      </aside>
      <main className="content">
        <header className="topbar">
          <h1>{TABS.find((tabItem) => tabItem.id === tab)?.label}</h1>
        </header>
        {!settings.token ? (
          <Banner kind="warn">
            Токен доступа не задан — введённые данные не сохранятся. Укажите адрес API и токен в{" "}
            <Button variant="primary" onClick={() => selectTab("settings")}>
              настройках
            </Button>
          </Banner>
        ) : null}
        <div className="view">
          {tab === "profile" ? <ProfileView /> : null}
          {tab === "matches" ? <MatchesView /> : null}
          {tab === "analysis" ? <AnalysisView /> : null}
          {tab === "autonomy" ? <AutonomyView /> : null}
          {tab === "decisions" ? <DecisionsView /> : null}
          {tab === "dynamics" ? <DynamicsView /> : null}
          {tab === "memory" ? <MemoryView /> : null}
          {tab === "vision" ? <VisionView /> : null}
          {tab === "journal" ? <JournalView /> : null}
          {tab === "emulator" ? <EmulatorView /> : null}
          {tab === "admin" ? <AdminView /> : null}
          {tab === "privacy" ? <PrivacyView /> : null}
          {tab === "settings" ? <SettingsView /> : null}
        </div>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <AppProvider>
      <Shell />
    </AppProvider>
  );
}
