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
import { ApiError, errorMessage } from "../lib/api";
import { useAsyncData } from "../lib/hooks";
import { AUTONOMY_MODES, type AutonomyMode } from "../lib/settings";
import type { Conversation, Draft } from "../lib/types";

function autonomyTone(mode: string): string {
  switch (mode) {
    case "auto_send":
      return "ok";
    case "suggest":
      return "info";
    case "paused":
      return "warn";
    default:
      return "neutral";
  }
}

function CreateConversation({ onCreated }: { onCreated: (conversation: Conversation) => void }) {
  const { api, settings, logJournal } = useApp();
  const [matchId, setMatchId] = useState("");
  const [mode, setMode] = useState<AutonomyMode>(settings.autonomyMode);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const conversation = await api.createConversation({
        match_id: matchId.trim() === "" ? null : matchId.trim(),
        autonomy_mode: mode,
      });
      logJournal("conversation", "Создан разговор", conversation.id);
      onCreated(conversation);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="nested">
      <Field label="ID знакомства (match_id, UUID)" hint="Необязательно.">
        <input
          className="input"
          value={matchId}
          placeholder="00000000-0000-0000-0000-000000000000"
          onChange={(event) => setMatchId(event.currentTarget.value)}
        />
      </Field>
      <Field label="Режим автономности">
        <Select
          value={mode}
          onChange={(value) => setMode(value as AutonomyMode)}
          options={AUTONOMY_MODES.map((item) => ({ value: item.id, label: item.title }))}
        />
      </Field>
      {error ? <Banner kind="error">{error}</Banner> : null}
      <Button variant="primary" onClick={() => void submit()} disabled={busy}>
        {busy ? "Создаём…" : "Создать разговор"}
      </Button>
    </div>
  );
}

function ConversationPanel({ conversationId }: { conversationId: string }) {
  const { api, logJournal, queueRequest } = useApp();
  const messages = useAsyncData(() => api.listMessages(conversationId), [api, conversationId]);

  const [direction, setDirection] = useState("inbound");
  const [text, setText] = useState("");
  const [importBusy, setImportBusy] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);

  const [draft, setDraft] = useState<Draft | null>(null);
  const [draftBusy, setDraftBusy] = useState(false);
  const [draftError, setDraftError] = useState<string | null>(null);

  async function importMessage(value: string, dir: string) {
    if (!value.trim()) return;
    setImportBusy(true);
    setImportError(null);
    try {
      await api.importMessage(conversationId, {
        content: value.trim(),
        direction: dir === "outbound" ? "outbound" : "inbound",
      });
      logJournal("message", `Импортировано ${dir === "outbound" ? "исходящее" : "входящее"} сообщение`);
      setText("");
      messages.reload();
    } catch (err) {
      if (err instanceof ApiError && err.status === 0) {
        await queueRequest({
          method: "POST",
          path: `/api/v1/conversations/${conversationId}/messages/import`,
          body: JSON.stringify({
            content: value.trim(),
            direction: dir === "outbound" ? "outbound" : "inbound",
          }),
          label: dir === "outbound" ? "отправка сообщения" : "импорт сообщения",
        });
        logJournal("outbox", "Нет связи с API — сообщение сохранено в оффлайн-очереди");
        setText("");
      } else {
        setImportError(errorMessage(err));
      }
    } finally {
      setImportBusy(false);
    }
  }

  async function generateDraft() {
    setDraftBusy(true);
    setDraftError(null);
    try {
      const result = await api.createDraft(conversationId);
      setDraft(result);
      logJournal(
        "draft",
        "Сгенерирован черновик",
        `${result.provider} · ${result.model} · ${result.latency_ms} мс`,
      );
    } catch (err) {
      setDraftError(errorMessage(err));
    } finally {
      setDraftBusy(false);
    }
  }

  return (
    <Section
      title="Диалог"
      description={`Разговор ${conversationId.slice(0, 8)} · черновик не отправляется сервером автоматически.`}
      actions={
        <Button variant="primary" onClick={() => void generateDraft()} disabled={draftBusy}>
          {draftBusy ? "Генерация…" : "Сгенерировать черновик"}
        </Button>
      }
    >
      {messages.loading ? <Loader label="Загружаем сообщения…" /> : null}
      {messages.error ? <Banner kind="error">{messages.error}</Banner> : null}
      {messages.data && messages.data.length === 0 ? (
        <EmptyState>Сообщений пока нет. Импортируйте первое сообщение ниже.</EmptyState>
      ) : null}

      <div className="messages">
        {messages.data?.map((message) => (
          <div key={message.id} className={`message message-${message.direction}`}>
            <div className="message-meta">
              <Badge tone={message.direction === "inbound" ? "info" : "ok"}>
                {message.direction === "inbound" ? "Собеседник" : "Пользователь"}
              </Badge>
              <span className="muted">{new Date(message.created_at).toLocaleString()}</span>
            </div>
            <p>{message.content}</p>
          </div>
        ))}
      </div>

      <div className="nested">
        <div className="row">
          <Select
            value={direction}
            onChange={setDirection}
            options={[
              { value: "inbound", label: "Входящее (от собеседника)" },
              { value: "outbound", label: "Исходящее (от пользователя)" },
            ]}
          />
        </div>
        <TextArea
          value={text}
          onChange={setText}
          rows={3}
          placeholder="Текст сообщения для импорта…"
        />
        {importError ? <Banner kind="error">{importError}</Banner> : null}
        <Button onClick={() => void importMessage(text, direction)} disabled={importBusy}>
          {importBusy ? "Импортируем…" : "Импортировать сообщение"}
        </Button>
      </div>

      {draftError ? <Banner kind="error">{draftError}</Banner> : null}
      {draft ? (
        <div className="nested">
          <div className="row">
            <Badge tone={draft.validation_ok ? "ok" : "warn"}>
              {draft.validation_ok ? "Проверка пройдена" : "Есть замечания"}
            </Badge>
            <span className="muted">
              {draft.provider} · {draft.model} · {draft.latency_ms} мс
            </span>
          </div>
          <blockquote className="draft">{draft.text}</blockquote>
          {draft.issues.length > 0 ? (
            <Banner kind="warn">Замечания: {draft.issues.join("; ")}</Banner>
          ) : null}
          <Button onClick={() => void importMessage(draft.text, "outbound")}>
            Использовать как исходящее сообщение
          </Button>
        </div>
      ) : null}
    </Section>
  );
}

export function MatchesView() {
  const { api } = useApp();
  const conversations = useAsyncData(() => api.listConversations(), [api]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  return (
    <div className="split">
      <div className="split-side">
        <Section
          title="Знакомства"
          actions={
            <Button onClick={() => setShowCreate((value) => !value)}>
              {showCreate ? "Отмена" : "+ Новый"}
            </Button>
          }
        >
          {showCreate ? (
            <CreateConversation
              onCreated={(conversation) => {
                setShowCreate(false);
                conversations.reload();
                setSelectedId(conversation.id);
              }}
            />
          ) : null}
          {conversations.loading ? <Loader /> : null}
          {conversations.error ? <Banner kind="error">{conversations.error}</Banner> : null}
          {conversations.data && conversations.data.length === 0 ? (
            <EmptyState>Разговоров пока нет.</EmptyState>
          ) : null}
          <ul className="list">
            {conversations.data?.map((conversation) => (
              <li key={conversation.id}>
                <button
                  type="button"
                  className={`list-item ${conversation.id === selectedId ? "active" : ""}`}
                  onClick={() => setSelectedId(conversation.id)}
                >
                  <span className="list-title">
                    {conversation.match_id
                      ? `match ${conversation.match_id.slice(0, 8)}`
                      : `диалог ${conversation.id.slice(0, 8)}`}
                  </span>
                  <Badge tone={autonomyTone(conversation.autonomy_mode)}>
                    {conversation.autonomy_mode}
                  </Badge>
                </button>
              </li>
            ))}
          </ul>
        </Section>
      </div>
      <div className="split-main">
        {selectedId ? (
          <ConversationPanel key={selectedId} conversationId={selectedId} />
        ) : (
          <EmptyState>Выберите разговор слева или создайте новый.</EmptyState>
        )}
      </div>
    </div>
  );
}
