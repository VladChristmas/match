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
  TextInput,
} from "../components/ui";
import { useApp } from "../context/AppContext";
import {
  addMemory,
  classifyMemory,
  correctMemory,
  deleteMemory,
  listMemory,
  memoryEvents,
  storageSupported,
  verifyMemory,
} from "../lib/storage";
import { useAsyncData } from "../lib/hooks";
import type { Memory, MemoryEvent, MemoryKind, MemoryStatus } from "../lib/types";

const KINDS: { value: MemoryKind; label: string }[] = [
  { value: "fact", label: "Факт" },
  { value: "preference", label: "Предпочтение" },
  { value: "hypothesis", label: "Гипотеза" },
  { value: "temporary_state", label: "Временное состояние" },
  { value: "agreement", label: "Договорённость" },
];

const STATUS_LABEL: Record<MemoryStatus, string> = {
  received: "получено",
  classified: "классифицировано",
  verified: "подтверждено",
  used: "использовано",
  revised: "пересмотрено",
};

export function MemoryView() {
  const { settings, logJournal } = useApp();
  const userId = settings.localUserId;
  const supported = storageSupported();

  const memories = useAsyncData(() => listMemory(userId), [userId]);
  const [events, setEvents] = useState<Record<string, MemoryEvent[]>>({});
  const [expanded, setExpanded] = useState<string | null>(null);

  const [kind, setKind] = useState<MemoryKind>("fact");
  const [content, setContent] = useState("");
  const [confidence, setConfidence] = useState("0.7");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function create() {
    const trimmed = content.trim();
    if (!trimmed) {
      setError("Введите содержание");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await addMemory(userId, {
        kind,
        content: trimmed,
        confidence: Number(confidence) || 0.5,
        source: "user",
      });
      setContent("");
      logJournal("memory", "Добавлено воспоминание", trimmed.slice(0, 80));
      memories.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function act(
    action: (id: string) => Promise<Memory | null>,
    id: string,
    summary: string,
  ) {
    setError(null);
    try {
      await action(id);
      logJournal("memory", summary, id);
      memories.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function toggleEvents(memoryId: string) {
    if (expanded === memoryId) {
      setExpanded(null);
      return;
    }
    setExpanded(memoryId);
    try {
      const items = await memoryEvents(memoryId);
      setEvents((prev) => ({ ...prev, [memoryId]: items }));
    } catch {
      setEvents((prev) => ({ ...prev, [memoryId]: [] }));
    }
  }

  async function remove(memoryId: string) {
    setError(null);
    try {
      await deleteMemory(userId, memoryId);
      logJournal("memory", "Удалено воспоминание", memoryId);
      memories.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <>
      {error ? <Banner kind="error">{error}</Banner> : null}
      {!supported ? (
        <Banner kind="warn">
          Локальная память доступна только в установленном приложении (Tauri). В браузере данные не
          сохраняются.
        </Banner>
      ) : null}

      <Section
        title="Долгосрочная память"
        description="Устойчивые сведения, гипотезы и договорённости хранятся локально на устройстве. Агент различает факты и предположения, вы видите происхождение и можете исправлять."
      >
        <Banner kind="info">
          Память живёт на этом устройстве и не отправляется на сервер (OQ-10, ADR-0030). Удаление
          воспоминания удаляет его из журнала.
        </Banner>
      </Section>

      <Section title="Новое воспоминание">
        <div className="stack">
          <Select
            value={kind}
            onChange={(value) => setKind(value as MemoryKind)}
            options={KINDS}
          />
          <TextArea
            rows={3}
            value={content}
            onChange={setContent}
            placeholder="Например: предпочитает короткие сообщения после рабочего дня"
          />
          <Field label="Уверенность (0–1)">
            <TextInput value={confidence} onChange={setConfidence} placeholder="0.7" />
          </Field>
          <Button variant="primary" onClick={() => void create()} disabled={!supported || busy}>
            Добавить
          </Button>
        </div>
      </Section>

      <Section
        title="Сохранённые воспоминания"
        description="Статус жизненного цикла: получено → классифицировано → подтверждено → использовано → пересмотрено."
        actions={<Button onClick={() => memories.reload()}>Обновить</Button>}
      >
        {memories.loading ? <Loader /> : null}
        {memories.error ? <Banner kind="error">{memories.error}</Banner> : null}
        {memories.data && memories.data.length === 0 && !memories.loading ? (
          <EmptyState>Память пуста. Добавьте первое воспоминание выше.</EmptyState>
        ) : null}
        <ul className="plain-list">
          {memories.data?.map((memory) => (
            <li key={memory.id}>
              <div className="row">
                <Badge tone={memory.status === "verified" ? "ok" : "neutral"}>
                  {STATUS_LABEL[memory.status]}
                </Badge>
                <Badge tone="neutral">{memory.kind}</Badge>
                <span className="muted">уверенность {memory.confidence.toFixed(2)}</span>
                <span className="muted">источник: {memory.source}</span>
                {memory.valid_until ? (
                  <span className="muted">актуально до {memory.valid_until.slice(0, 10)}</span>
                ) : null}
              </div>
              <p>{memory.content}</p>
              <div className="row">
                {memory.status !== "classified" && memory.status !== "verified" ? (
                  <Button
                    onClick={() =>
                      void act((id) => classifyMemory(userId, id, memory.kind), memory.id, "Классифицировано воспоминание")
                    }
                  >
                    Классифицировать
                  </Button>
                ) : null}
                {memory.status !== "verified" ? (
                  <Button onClick={() => void act((id) => verifyMemory(userId, id), memory.id, "Подтверждено воспоминание")}>
                    Подтвердить
                  </Button>
                ) : null}
                <Button
                  variant="danger"
                  onClick={() =>
                    void act(
                      (id) =>
                        correctMemory(userId, id, {
                          content: memory.content,
                          confidence: memory.confidence,
                        }),
                      memory.id,
                      "Воспоминание отмечено пересмотренным",
                    )
                  }
                >
                  Отметить пересмотренным
                </Button>
                <Button variant="danger" onClick={() => void remove(memory.id)}>
                  Удалить
                </Button>
                <Button onClick={() => void toggleEvents(memory.id)}>
                  {expanded === memory.id ? "Скрыть историю" : "История изменений"}
                </Button>
              </div>
              {expanded === memory.id ? (
                <ul className="plain-list">
                  {(events[memory.id] ?? []).map((event) => (
                    <li key={event.id} className="row">
                      <Badge tone="neutral">{event.event_type}</Badge>
                      <span className="muted">{event.created_at}</span>
                      {event.detail ? <span className="muted">{event.detail}</span> : null}
                    </li>
                  ))}
                  {(events[memory.id] ?? []).length === 0 ? (
                    <li className="muted">Событий нет.</li>
                  ) : null}
                </ul>
              ) : null}
            </li>
          ))}
        </ul>
      </Section>
    </>
  );
}
