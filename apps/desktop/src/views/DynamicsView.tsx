import { useState } from "react";

import { Badge, Banner, Button, EmptyState, Loader, Section, Select } from "../components/ui";
import { useApp } from "../context/AppContext";
import { errorMessage } from "../lib/api";
import { useAsyncData } from "../lib/hooks";

const DIMENSIONS = [
  ["mutuality", "Взаимность"],
  ["consistency", "Последовательность"],
  ["emotional_comfort", "Эмоциональный комфорт"],
  ["expectations_fit", "Совместимость ожиданий"],
  ["negotiation_ability", "Договороспособность"],
  ["relationship_development", "Развитие знакомства"],
] as const;

function dimensionLabel(dimension: string): string {
  return DIMENSIONS.find(([value]) => value === dimension)?.[1] ?? dimension;
}

export function DynamicsView() {
  const { api, logJournal } = useApp();
  const conversations = useAsyncData(() => api.listConversations(), [api]);
  const [conversationId, setConversationId] = useState("");

  const signals = useAsyncData(
    () =>
      conversationId
        ? api.listDynamicsSignals(conversationId)
        : Promise.resolve([] as never[]),
    [api, conversationId],
  );
  const timeline = useAsyncData(
    () => (conversationId ? api.listDynamicsTimeline(conversationId) : Promise.resolve([] as never[])),
    [api, conversationId],
  );
  const comparison = useAsyncData(
    () =>
      conversationId
        ? api.compareDynamicsPeriods(conversationId)
        : Promise.resolve([] as never[]),
    [api, conversationId],
  );

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  async function compute() {
    if (!conversationId) {
      setError("Выберите разговор");
      return;
    }
    setBusy(true);
    setError(null);
    setNote(null);
    try {
      const fresh = await api.computeDynamicsSignals(conversationId);
      setNote(`Сигналы пересчитаны: ${fresh.length} измерений.`);
      logJournal("dynamics", "Пересчитана динамика отношений", conversationId);
      signals.reload();
      comparison.reload();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const latestByDimension = new Map<string, { value: number; observed_at: string }>();
  for (const signal of signals.data ?? []) {
    const current = latestByDimension.get(signal.dimension);
    if (!current || signal.observed_at > current.observed_at) {
      latestByDimension.set(signal.dimension, {
        value: signal.value,
        observed_at: signal.observed_at,
      });
    }
  }

  return (
    <>
      {error ? <Banner kind="error">{error}</Banner> : null}
      {note ? <Banner kind="success">{note}</Banner> : null}

      <Section
        title="Динамика отношений"
        description="Шесть независимых измерений динамики общения за 90 дней. Без сводного «магического балла»: у каждого значения есть основания."
        actions={
          <Button variant="primary" onClick={() => void compute()} disabled={busy}>
            {busy ? "Пересчитываю…" : "Пересчитать сигналы"}
          </Button>
        }
      >
        <Select
          value={conversationId}
          onChange={setConversationId}
          options={[
            { value: "", label: "Выберите разговор…" },
            ...(conversations.data ?? []).map((item) => ({
              value: item.id,
              label: `диалог ${item.id.slice(0, 8)}`,
            })),
          ]}
        />
      </Section>

      {conversationId ? (
        <>
          <Section title="Измерения" description="Последние значения и дата наблюдения.">
            {signals.loading ? <Loader /> : null}
            {signals.error ? <Banner kind="error">{signals.error}</Banner> : null}
            {latestByDimension.size === 0 && !signals.loading ? (
              <EmptyState>
                Недостаточно наблюдений — система не делает категоричных выводов по пустым данным.
              </EmptyState>
            ) : null}
            <ul className="plain-list">
              {[...latestByDimension.entries()].map(([dimension, state]) => (
                <li key={dimension} className="row">
                  <span className="list-title">{dimensionLabel(dimension)}</span>
                  <Badge tone="neutral">{state.value.toFixed(2)}</Badge>
                  <span className="muted">наблюдение {state.observed_at.slice(0, 10)}</span>
                </li>
              ))}
            </ul>
          </Section>

          <Section title="Изменение между периодами" description="Текущие 30 дней против предыдущих 30 дней.">
            {comparison.loading ? <Loader /> : null}
            {comparison.error ? <Banner kind="error">{comparison.error}</Banner> : null}
            {comparison.data && comparison.data.length === 0 && !comparison.loading ? (
              <EmptyState>Значимых изменений между периодами не выявлено.</EmptyState>
            ) : null}
            <ul className="plain-list">
              {comparison.data?.map((change, index) => (
                <li key={index} className="row">
                  <span className="list-title">
                    {dimensionLabel(String(change.dimension ?? "—"))}
                  </span>
                  <Badge tone={change.direction === "improved" ? "ok" : "warn"}>
                    Δ {Number(change.delta ?? 0).toFixed(2)}
                  </Badge>
                  <span className="muted">
                    {Number(change.before ?? 0).toFixed(2)} → {Number(change.after ?? 0).toFixed(2)}
                  </span>
                </li>
              ))}
            </ul>
          </Section>

          <Section title="Поворотные моменты" description="Зафиксированные переломные события общения.">
            {timeline.loading ? <Loader /> : null}
            {timeline.error ? <Banner kind="error">{timeline.error}</Banner> : null}
            {timeline.data && timeline.data.length === 0 && !timeline.loading ? (
              <EmptyState>Поворотных моментов не записано.</EmptyState>
            ) : null}
            <ul className="plain-list">
              {timeline.data?.map((entry) => (
                <li key={entry.id}>
                  <div className="row">
                    <Badge tone="neutral">{entry.event_type}</Badge>
                    <span className="muted">{entry.created_at.slice(0, 10)}</span>
                  </div>
                  <p>{entry.description}</p>
                </li>
              ))}
            </ul>
          </Section>
        </>
      ) : null}
    </>
  );
}
