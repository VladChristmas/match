import { useState } from "react";

import { Banner, Button, Loader, Section } from "../components/ui";
import { useApp } from "../context/AppContext";
import { errorMessage } from "../lib/api";
import { useAsyncData } from "../lib/hooks";

function downloadJson(data: unknown): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `match-export-${new Date().toISOString().slice(0, 10)}.json`;
  link.click();
  URL.revokeObjectURL(url);
}

function countEntries(value: unknown): [string, number][] {
  if (!value || typeof value !== "object") return [];
  return Object.entries(value as Record<string, unknown>)
    .filter(([, item]) => Array.isArray(item))
    .map(([key, item]) => [key, (item as unknown[]).length]);
}

export function PrivacyView() {
  const { api, logJournal } = useApp();
  const exported = useAsyncData(() => api.exportPrivacy(), [api]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [armed, setArmed] = useState(false);
  const [deleted, setDeleted] = useState(false);

  async function deleteAll() {
    setBusy(true);
    setError(null);
    try {
      await api.requestDeletion();
      setDeleted(true);
      setArmed(false);
      logJournal("privacy", "Запрошено удаление всех данных");
      exported.reload();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const counts = exported.data ? countEntries(exported.data) : [];

  return (
    <>
      {error ? <Banner kind="error">{error}</Banner> : null}
      {deleted ? (
        <Banner kind="success">
          Удаление выполнено: профиль, диалоги, память, токены и observations удалены с сервера.
        </Banner>
      ) : null}

      <Section
        title="Ваши данные"
        description="Экспорт показывает всё, что сервер хранит о вас. Экспорт не содержит значения токенов доступа."
        actions={
          <>
            <Button onClick={() => exported.reload()}>Обновить</Button>
            <Button
              variant="primary"
              onClick={() => exported.data && downloadJson(exported.data)}
              disabled={!exported.data}
            >
              Скачать JSON
            </Button>
          </>
        }
      >
        {exported.loading ? <Loader /> : null}
        {exported.error ? <Banner kind="error">{exported.error}</Banner> : null}
        {exported.data ? (
          counts.length > 0 ? (
            <ul className="plain-list">
              {counts.map(([key, count]) => (
                <li key={key} className="row">
                  <span className="list-title">{key}</span>
                  <span className="muted">{count}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Данных нет.</p>
          )
        ) : null}
      </Section>

      <Section
        title="Удаление данных"
        description="Необратимо: удаляет профиль, диалоги, сообщения, оценки, память, токены и vision-наблюдения."
      >
        {armed ? (
          <div className="row">
            <Banner kind="warn">
              Подтвердите удаление — действие нельзя отменить. Локальная память на устройстве остаётся
              (удаляйте её на экране «Память»).
            </Banner>
            <Button variant="danger" onClick={() => void deleteAll()} disabled={busy}>
              {busy ? "Удаляю…" : "Да, удалить всё"}
            </Button>
            <Button onClick={() => setArmed(false)}>Отмена</Button>
          </div>
        ) : (
          <Button variant="danger" onClick={() => setArmed(true)} disabled={busy}>
            Удалить все данные…
          </Button>
        )}
      </Section>
    </>
  );
}
