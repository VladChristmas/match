import { Badge, Banner, EmptyState, Loader, Section } from "../components/ui";
import { useApp } from "../context/AppContext";
import { useAsyncData } from "../lib/hooks";
import { AUTONOMY_MODES, type AutonomyMode } from "../lib/settings";

export function AutonomyView() {
  const { settings, update, api, logJournal } = useApp();
  const conversations = useAsyncData(() => api.listConversations(), [api]);

  function choose(mode: AutonomyMode) {
    if (mode === settings.autonomyMode) return;
    update({ autonomyMode: mode });
    logJournal("autonomy", "Режим автономности по умолчанию изменён", mode);
  }

  return (
    <>
      <Section
        title="Режим автономности"
        description="Режим по умолчанию для новых разговоров. Управление очередью и паузой на сервере появится на Этапе 8."
      >
        <div className="mode-grid">
          {AUTONOMY_MODES.map((mode) => (
            <button
              key={mode.id}
              type="button"
              className={`mode-card ${settings.autonomyMode === mode.id ? "active" : ""}`}
              onClick={() => choose(mode.id)}
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
        title="Разговоры"
        description="Текущий режим каждого разговора. Режим задаётся при создании разговора."
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
          В режиме «Черновик на подтверждение» агент останавливается и передаёт управление вам. То, что
          черновик не отправляется сервером, — осознанное ограничение: прямые действия выполняет только
          пользователь, пока не включён Этап 8.
        </Banner>
      </Section>
    </>
  );
}
