import { useState } from "react";

import { AppProvider, useApp } from "./context/AppContext";
import { AdminView } from "./views/AdminView";
import { AnalysisView } from "./views/AnalysisView";
import { AutonomyView } from "./views/AutonomyView";
import { JournalView } from "./views/JournalView";
import { MatchesView } from "./views/MatchesView";
import { ProfileView } from "./views/ProfileView";
import { SettingsView } from "./views/SettingsView";
import { VisionView } from "./views/VisionView";
import "./styles.css";

type Tab =
  | "profile"
  | "matches"
  | "analysis"
  | "autonomy"
  | "vision"
  | "journal"
  | "admin"
  | "settings";

const TABS: { id: Tab; label: string }[] = [
  { id: "profile", label: "Профиль" },
  { id: "matches", label: "Знакомства" },
  { id: "analysis", label: "Анализ" },
  { id: "autonomy", label: "Автономность" },
  { id: "vision", label: "Зрение" },
  { id: "journal", label: "Журнал" },
  { id: "admin", label: "Админ" },
  { id: "settings", label: "Настройки" },
];

function Shell() {
  const { ready, settings } = useApp();
  const [tab, setTab] = useState<Tab>("profile");

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
              onClick={() => setTab(item.id)}
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
        <div className="view">
          {tab === "profile" ? <ProfileView /> : null}
          {tab === "matches" ? <MatchesView /> : null}
          {tab === "analysis" ? <AnalysisView /> : null}
          {tab === "autonomy" ? <AutonomyView /> : null}
          {tab === "vision" ? <VisionView /> : null}
          {tab === "journal" ? <JournalView /> : null}
          {tab === "admin" ? <AdminView /> : null}
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
