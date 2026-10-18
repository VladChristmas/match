import { useState } from "react";

import {
  Badge,
  Banner,
  Button,
  EmptyState,
  Field,
  Loader,
  Section,
  Select,
  TextArea,
} from "../components/ui";
import { useApp } from "../context/AppContext";
import { errorMessage } from "../lib/api";
import { useAsyncData } from "../lib/hooks";

const FEEDBACK_TYPES = [
  { value: "rating", label: "Оценка ответа" },
  { value: "correction", label: "Исправление" },
  { value: "flag", label: "Проблема / риск" },
];

export function JournalView() {
  const { api, settings, clearJournal, logJournal } = useApp();
  const feedback = useAsyncData(() => api.listFeedback(), [api]);
  const conversations = useAsyncData(() => api.listConversations(), [api]);

  const [type, setType] = useState("rating");
  const [rating, setRating] = useState("5");
  const [correction, setCorrection] = useState("");
  const [conversationId, setConversationId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const conversationOptions = [
    { value: "", label: "Без привязки" },
    ...(conversations.data ?? []).map((item) => ({
      value: item.id,
      label: item.match_id ? `match ${item.match_id.slice(0, 8)}` : `диалог ${item.id.slice(0, 8)}`,
    })),
  ];

  async function submitFeedback() {
    setBusy(true);
    setError(null);
    try {
      await api.createFeedback({
        feedback_type: type,
        rating: rating.trim() === "" ? null : Number(rating),
        correction: correction.trim() === "" ? null : correction.trim(),
        conversation_id: conversationId || null,
      });
      logJournal("feedback", "Отправлена обратная связь", type);
      setCorrection("");
      feedback.reload();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Section
        title="Обратная связь"
        description="Коррекции помогают агенту учиться писать в вашем стиле. Психопрофиль собеседника виден только вам."
      >
        <div className="grid-2">
          <Field label="Тип обратной связи">
            <Select value={type} onChange={setType} options={FEEDBACK_TYPES} />
          </Field>
          <Field label="Оценка (1–5)" hint="Для типа «Оценка ответа».">
            <input
              className="input"
              type="number"
              min={1}
              max={5}
              value={rating}
              onChange={(event) => setRating(event.currentTarget.value)}
            />
          </Field>
        </div>
        <Field label="Разговор">
          <Select value={conversationId} onChange={setConversationId} options={conversationOptions} />
        </Field>
        <Field label="Комментарий / исправление">
          <TextArea value={correction} onChange={setCorrection} rows={3} placeholder="Что стоит поправить…" />
        </Field>
        {error ? <Banner kind="error">{error}</Banner> : null}
        <Button variant="primary" onClick={() => void submitFeedback()} disabled={busy}>
          {busy ? "Отправляем…" : "Отправить обратную связь"}
        </Button>
      </Section>

      <Section title="Обратная связь с сервера">
        {feedback.loading ? <Loader /> : null}
        {feedback.error ? <Banner kind="error">{feedback.error}</Banner> : null}
        {feedback.data && feedback.data.length === 0 ? (
          <EmptyState>Записей пока нет.</EmptyState>
        ) : null}
        <ul className="plain-list">
          {feedback.data?.map((item) => (
            <li key={item.id} className="row">
              <Badge tone="info">{item.feedback_type}</Badge>
              {item.rating !== null ? <Badge tone="neutral">{item.rating}/5</Badge> : null}
              <span>{item.correction ?? "—"}</span>
              <span className="muted">{new Date(item.created_at).toLocaleString()}</span>
            </li>
          ))}
        </ul>
      </Section>

      <Section
        title="Локальный журнал действий"
        description="Действия в приложении. Хранится на устройстве."
        actions={
          <Button variant="danger" onClick={clearJournal} disabled={settings.journal.length === 0}>
            Очистить
          </Button>
        }
      >
        {settings.journal.length === 0 ? <EmptyState>Журнал пуст.</EmptyState> : null}
        <ul className="plain-list">
          {settings.journal.map((entry) => (
            <li key={entry.id} className="row">
              <Badge tone="neutral">{entry.kind}</Badge>
              <span>{entry.summary}</span>
              {entry.detail ? <span className="muted">{entry.detail}</span> : null}
              <span className="muted">{new Date(entry.at).toLocaleString()}</span>
            </li>
          ))}
        </ul>
      </Section>
    </>
  );
}
