import { useState } from "react";

import { Badge, Banner, Button, EmptyState, Loader, Section } from "../components/ui";
import { useApp } from "../context/AppContext";
import { errorMessage } from "../lib/api";
import { useAsyncData } from "../lib/hooks";
import { AUTONOMY_MODES, type AutonomyMode } from "../lib/settings";

export function AutonomyView() {
  const { settings, update, api, logJournal } = useApp();
  const agentSettings = useAsyncData(() => api.getAgentSettings(), [api]);
  const conversations = useAsyncData(() => api.listConversations(), [api]);
  const pending = useAsyncData(() => api.listActions("pending"), [api]);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const paused = agentSettings.data?.queue_paused ?? false;

  async function choose(mode: AutonomyMode) {
    if (mode === settings.autonomyMode) return;
    update({ autonomyMode: mode });
    logJournal("autonomy", "Режим автономности по умолчанию изменён", mode);
    setError(null);
    try {
      await api.updateAgentSettings({ default_autonomy_mode: mode });
      agentSettings.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  async function togglePause() {
    setBusy(true);
    setError(null);
    try {
      if (paused) {
        await api.resumeAgent();
        logJournal("autonomy", "Очередь агента возобновлена");
      } else {
        await api.pauseAgent();
        logJournal("autonomy", "Очередь агента поставлена на паузу");
      }
      agentSettings.reload();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function decide(actionId: string, approve: boolean) {
    setError(null);
    try {
      if (approve) {
        await api.approveAction(actionId);
        logJournal("autonomy", "Действие одобрено и отправлено", actionId);
      } else {
        await api.rejectAction(actionId);
        logJournal("autonomy", "Действие отклонено", actionId);
      }
      pending.reload();
      conversations.reload();
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <>
      {error ? <Banner kind="error">{error}</Banner> : null}

      <Section
        title="Состояние агента"
        description="Общая пауза останавливает авто-отправку для всех разговоров."
        actions={
          <Button variant={paused ? "primary" : "danger"} onClick={() => void togglePause()} disabled={busy}>
            {paused ? "Возобновить" : "Поставить на паузу"}
          </Button>
        }
      >
        {agentSettings.loading ? <Loader /> : null}
        {agentSettings.error ? (
          <Banner kind="error">{agentSettings.error}</Banner>
        ) : null}
        {agentSettings.data ? (
          <div className="row">
            <Badge tone={paused ? "warn" : "ok"}>{paused ? "пауза" : "активен"}</Badge>
            <span className="muted">
              Режим по умолчанию: {agentSettings.data.default_autonomy_mode}
            </span>
          </div>
        ) : null}
      </Section>

      <Section
        title="Режим автономности по умолчанию"
        description="Применяется к новым разговорам. Режим конкретного разговора задаётся при создании."
      >
        <div className="mode-grid">
          {AUTONOMY_MODES.map((mode) => (
            <button
              key={mode.id}
              type="button"
              className={`mode-card ${settings.autonomyMode === mode.id ? "active" : ""}`}
              onClick={() => void choose(mode.id)}
            >
              <div className="mode-head">
                <span className="mode-title">{mode.title}</span>
                {settings.autonomyMode === mode.id ? <Badge tone="ok">выбран</Badge> : null}
              </div>
              <p className="muted">{mode.description}</p>
            </button>
          ))}
        </div>
      </Section>

      <Section
        title="Очередь на подтверждение"
        description="Действия, ожидающие решения человека (передача человеку)."
        actions={<Button onClick={() => pending.reload()}>Обновить</Button>}
      >
        {pending.loading ? <Loader /> : null}
        {pending.error ? <Banner kind="error">{pending.error}</Banner> : null}
        {pending.data && pending.data.length === 0 ? (
          <EmptyState>Очередь пуста.</EmptyState>
        ) : null}
        <ul className="plain-list">
          {pending.data?.map((action) => (
            <li key={action.id}>
              <div className="row">
                <Badge tone="warn">{action.status}</Badge>
                <span className="list-title">диалог {action.conversation_id.slice(0, 8)}</span>
                {action.validation_ok === false ? <Badge tone="error">замечания</Badge> : null}
              </div>
              <p>{action.text ?? "—"}</p>
              <div className="row">
                <Button variant="primary" onClick={() => void decide(action.id, true)}>
                  Одобрить и отправить
                </Button>
                <Button variant="danger" onClick={() => void decide(action.id, false)}>
                  Отклонить
                </Button>
              </div>
            </li>
          ))}
        </ul>
      </Section>

      <Section
        title="Разговоры"
        description="Текущий режим каждого разговора."
      >
        {conversations.loading ? <Loader /> : null}
        {conversations.error ? <Banner kind="error">{conversations.error}</Banner> : null}
        {conversations.data && conversations.data.length === 0 ? (
          <EmptyState>Разговоров пока нет.</EmptyState>
        ) : null}
        <ul className="plain-list">
          {conversations.data?.map((item) => (
            <li key={item.id} className="row">
              <span className="list-title">
                {item.match_id ? `match ${item.match_id.slice(0, 8)}` : `диалог ${item.id.slice(0, 8)}`}
              </span>
              <Badge tone="neutral">{item.autonomy_mode}</Badge>
              <span className="muted">{item.status}</span>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Передача человеку">
        <Banner kind="info">
          Когда агент не уверен или авто-отправка выключена, действие попадает в очередь и ждёт вашего
          решения. Одобрение отправляет сообщение от вашего имени, отклонение — отменяет.
        </Banner>
      </Section>
    </>
  );
}
