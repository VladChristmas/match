import { useState } from "react";

import { Badge, Banner, Button, EmptyState, Loader, Section, Select, TextArea } from "../components/ui";
import { useApp } from "../context/AppContext";
import { errorMessage } from "../lib/api";
import { useAsyncData } from "../lib/hooks";

const MODE_TONE: Record<string, string> = {
  execute: "ok",
  verify: "warn",
  escalate: "warn",
  stop: "error",
};

function decisionTone(mode: string): string {
  return MODE_TONE[mode] ?? "neutral";
}

function formatEvidence(items: Record<string, unknown>[]): string {
  return items
    .map((item) =>
      Object.entries(item)
        .map(([key, value]) => `${key}: ${String(value)}`)
        .join(", "),
    )
    .join(" | ");
}

export function DecisionsView() {
  const { api, logJournal } = useApp();
  const conversations = useAsyncData(() => api.listConversations(), [api]);
  const decisions = useAsyncData(() => api.listDecisions(), [api]);

  const [conversationId, setConversationId] = useState("");
  const [triggerText, setTriggerText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  async function evaluate() {
    if (!conversationId) {
      setError("Выберите разговор");
      return;
    }
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const decision = await api.evaluateDecision({
        conversation_id: conversationId,
        trigger_text: triggerText.trim() ? triggerText.trim() : null,
      });
      setResult(
        `Решение без побочных эффектов: ${decision.action} (${decision.mode}), уверенность ${decision.confidence.toFixed(2)}`,
      );
      logJournal("decisions", "Оценено решение агента", decision.id);
      decisions.reload();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      {error ? <Banner kind="error">{error}</Banner> : null}
      {result ? <Banner kind="success">{result}</Banner> : null}

      <Section
        title="Оценить решение"
        description="Показывает, что агент сделал бы сейчас, без исполнения: вариант, режим, обоснование и уверенность."
      >
        <div className="stack">
          <Select
            value={conversationId}
            onChange={setConversationId}
            options={[
              { value: "", label: "Выберите разговор…" },
              ...(conversations.data ?? []).map((item) => ({
                value: item.id,
                label: `диалог ${item.id.slice(0, 8)} · ${item.autonomy_mode}`,
              })),
            ]}
          />
          <TextArea
            rows={3}
            value={triggerText}
            onChange={setTriggerText}
            placeholder="Входящее сообщение, которое стал бы триггером (необязательно)"
          />
          <Button variant="primary" onClick={() => void evaluate()} disabled={busy}>
            {busy ? "Оцениваю…" : "Оценить"}
          </Button>
        </div>
      </Section>

      <Section
        title="Журнал решений"
        description="Каждое решение агента: выбранное действие, альтернативы, основания и недостающие данные. Тексты переписки не хранятся."
        actions={<Button onClick={() => decisions.reload()}>Обновить</Button>}
      >
        {decisions.loading ? <Loader /> : null}
        {decisions.error ? <Banner kind="error">{decisions.error}</Banner> : null}
        {decisions.data && decisions.data.length === 0 ? (
          <EmptyState>Решений пока нет — они появятся после первых действий агента.</EmptyState>
        ) : null}
        <ul className="plain-list">
          {decisions.data?.map((decision) => (
            <li key={decision.id}>
              <div className="row">
                <Badge tone={decisionTone(decision.mode)}>{decision.mode}</Badge>
                <span className="list-title">{decision.action}</span>
                <span className="muted">уверенность {decision.confidence.toFixed(2)}</span>
                <span className="muted">диалог {decision.conversation_id.slice(0, 8)}</span>
              </div>
              <p>{decision.rationale}</p>
              {decision.alternatives.length > 0 ? (
                <p className="muted">Альтернативы: {formatEvidence(decision.alternatives)}</p>
              ) : null}
              {decision.evidence.length > 0 ? (
                <p className="muted">Основания: {formatEvidence(decision.evidence)}</p>
              ) : null}
              {decision.missing.length > 0 ? (
                <p className="muted">Не хватает данных: {decision.missing.join(", ")}</p>
              ) : null}
              {decision.escalation_reason ? (
                <Banner kind="warn">Передано человеку: {decision.escalation_reason}</Banner>
              ) : null}
            </li>
          ))}
        </ul>
      </Section>
    </>
  );
}
