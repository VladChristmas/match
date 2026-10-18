import { useState } from "react";

import { Badge, Banner, Button, EmptyState, Loader, Section, Select } from "../components/ui";
import { useApp } from "../context/AppContext";
import { errorMessage } from "../lib/api";
import { useAsyncData } from "../lib/hooks";
import { isTauri } from "../lib/settings";
import type { CaptureTarget, CapturedFrame } from "../lib/types";
import { captureWindowFrame, listCaptureWindows, pngDataUrl } from "../lib/vision";

export function VisionView() {
  const { settings, update, api, logJournal } = useApp();
  const conversations = useAsyncData(() => api.listConversations(), [api]);
  const observations = useAsyncData(() => api.listVisionObservations(), [api]);

  const [windows, setWindows] = useState<CaptureTarget[]>([]);
  const [loadingWindows, setLoadingWindows] = useState(false);
  const [frame, setFrame] = useState<CapturedFrame | null>(null);
  const [conversationId, setConversationId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const tauri = isTauri();
  const target = settings.visionTargetHandle;

  async function refreshWindows() {
    setLoadingWindows(true);
    setError(null);
    try {
      const found = await listCaptureWindows();
      setWindows(found);
      logJournal("vision", "Список окон обновлён", `${found.length} окон`);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoadingWindows(false);
    }
  }

  async function capture() {
    if (target === null) {
      setError("Сначала выберите окно для наблюдения.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const captured = await captureWindowFrame(target);
      setFrame(captured);
      logJournal(
        "vision",
        "Кадр снят",
        `${captured.width}×${captured.height}, ${settings.visionSourceLabel}`,
      );
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function send() {
    if (!frame) {
      setError("Сначала снимите кадр.");
      return;
    }
    if (!conversationId) {
      setError("Выберите разговор для привязки наблюдения.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const created = await api.createVisionObservation({
        conversation_id: conversationId,
        frame_base64: frame.png_base64,
        source_label: settings.visionSourceLabel,
        captured_at: new Date().toISOString(),
      });
      logJournal("vision", "Наблюдение отправлено на сервер", created.id);
      observations.reload();
      setFrame(null);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const windowOptions = windows.map((item) => ({
    value: String(item.handle),
    label: item.title,
  }));

  return (
    <>
      {error ? <Banner kind="error">{error}</Banner> : null}
      {!tauri ? (
        <Banner kind="warn">
          Захват экрана работает только в собранном приложении MATCH (Tauri). В браузере доступны лишь
          отправка и просмотр наблюдений.
        </Banner>
      ) : null}

      <Section
        title="Наблюдение за экраном"
        description="Кадр снимается через Windows.Graphics.Capture из выбранного окна. Изображение не сохраняется на диск; на сервер оно уходит только по вашей команде (ADR-0008/ADR-0007)."
        actions={
          <Button variant={settings.visionEnabled ? "danger" : "primary"} onClick={() => {
            const next = !settings.visionEnabled;
            update({ visionEnabled: next });
            logJournal("vision", next ? "Наблюдение включено" : "Наблюдение выключено");
          }}>
            {settings.visionEnabled ? "Выключить наблюдение" : "Включить наблюдение"}
          </Button>
        }
      >
        <div className="row">
          <Badge tone={settings.visionEnabled ? "ok" : "neutral"}>
            {settings.visionEnabled ? "наблюдение включено" : "наблюдение выключено"}
          </Badge>
          <span className="muted">
            {target === null ? "окно не выбрано" : `окно: ${settings.visionSourceLabel}`}
          </span>
        </div>
      </Section>

      <Section
        title="Окно для наблюдения"
        description="Выберите окно собеседника (браузер или приложение). Агент видит только то, что видно в этом окне."
        actions={
          <Button onClick={() => void refreshWindows()} disabled={loadingWindows || !tauri}>
            {loadingWindows ? "Поиск…" : "Обновить список окон"}
          </Button>
        }
      >
        {loadingWindows && windows.length === 0 ? <Loader label="Поиск окон…" /> : null}
        {windows.length === 0 ? (
          <EmptyState>{tauri ? "Список пуст — нажмите «Обновить»." : "Недоступно вне приложения."}</EmptyState>
        ) : (
          <Select
            value={target === null ? "" : String(target)}
            onChange={(value) => {
              const selected = windows.find((item) => String(item.handle) === value);
              update({
                visionTargetHandle: selected ? selected.handle : null,
                visionSourceLabel: selected ? selected.title : "window",
              });
            }}
            options={[{ value: "", label: "— не выбрано —" }, ...windowOptions]}
          />
        )}
      </Section>

      <Section
        title="Кадр"
        description="Снимите кадр и просмотрите его перед отправкой."
        actions={
          <div className="row">
            <Button onClick={() => void capture()} disabled={busy || target === null}>
              Снять кадр
            </Button>
            <Button
              variant="primary"
              onClick={() => void send()}
              disabled={busy || frame === null || !conversationId}
            >
              Отправить на анализ
            </Button>
          </div>
        }
      >
        <div className="row">
          <Select
            value={conversationId}
            onChange={setConversationId}
            options={[
              { value: "", label: "— выбрать разговор —" },
              ...(conversations.data ?? []).map((item) => ({
                value: item.id,
                label: item.match_id
                  ? `match ${item.match_id.slice(0, 8)}`
                  : `диалог ${item.id.slice(0, 8)}`,
              })),
            ]}
          />
        </div>
        {conversations.error ? <Banner kind="error">{conversations.error}</Banner> : null}
        {frame ? (
          <div className="frame">
            <img className="frame-preview" src={pngDataUrl(frame)} alt="Снятый кадр" />
            <span className="muted">
              {frame.width}×{frame.height}
            </span>
          </div>
        ) : (
          <EmptyState>Кадр ещё не снят.</EmptyState>
        )}
      </Section>

      <Section
        title="Наблюдения"
        description="Сервер хранит только метаданные кадра (размеры и отпечаток), без самого изображения."
        actions={<Button onClick={() => observations.reload()}>Обновить</Button>}
      >
        {observations.loading ? <Loader /> : null}
        {observations.error ? <Banner kind="error">{observations.error}</Banner> : null}
        {observations.data && observations.data.length === 0 ? (
          <EmptyState>Наблюдений пока нет.</EmptyState>
        ) : null}
        <ul className="plain-list">
          {observations.data?.map((item) => (
            <li key={item.id}>
              <div className="row">
                <Badge tone={item.analysis_pending ? "warn" : "ok"}>
                  {item.analysis_pending ? "ожидает анализа" : "проанализировано"}
                </Badge>
                <span className="list-title">
                  {item.frame_width}×{item.frame_height}
                </span>
                <span className="muted">{item.source_label}</span>
              </div>
              <span className="muted mono">{item.content_sha256.slice(0, 16)}…</span>
            </li>
          ))}
        </ul>
        <Banner kind="info">
          Анализ кадра мультимодальной моделью ждёт закрытия OQ-8, поэтому наблюдения пока только
          фиксируются.
        </Banner>
      </Section>
    </>
  );
}
