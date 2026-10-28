import { useEffect, useRef, useState } from "react";

import { Badge, Banner, Button, EmptyState, Loader, Section, Select } from "../components/ui";
import { useApp } from "../context/AppContext";
import { errorMessage } from "../lib/api";
import { simulatorFrameSource } from "../lib/emulator/frameSource";
import {
  DEMO_SCREENS,
  RESOLUTIONS,
  findResolution,
  type Orientation,
  type ScreenMode,
  type VirtualScreen,
} from "../lib/emulator/screen";
import { buildScene, paint } from "../lib/emulator/scene";
import { useAsyncData } from "../lib/hooks";
import type { Conversation, VisionObservation } from "../lib/types";

const SCREEN_MODES: { id: ScreenMode; label: string }[] = [
  { id: "matches", label: "Лента знакомств" },
  { id: "chat", label: "Переписка" },
  { id: "profile", label: "Профиль" },
  { id: "notification", label: "Уведомление" },
];

const ORIENTATIONS: { id: Orientation; label: string }[] = [
  { id: "portrait", label: "Портрет" },
  { id: "landscape", label: "Альбом" },
];

export function EmulatorView() {
  const { api, logJournal } = useApp();
  const conversations = useAsyncData(() => api.listConversations(), [api]);

  const [mode, setMode] = useState<ScreenMode>("chat");
  const [orientation, setOrientation] = useState<Orientation>("portrait");
  const [resolutionId, setResolutionId] = useState(RESOLUTIONS[0].id);
  const [scale, setScale] = useState(1);
  const [conversationId, setConversationId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastObservation, setLastObservation] = useState<VisionObservation | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const screen: VirtualScreen = DEMO_SCREENS[mode];
  const resolution = findResolution(resolutionId);
  const scene = buildScene(screen, { resolution, orientation });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    canvas.width = scene.width;
    canvas.height = scene.height;
    paint(ctx, scene, scale);
  }, [scene, scale]);

  async function sendFrame() {
    const canvas = canvasRef.current;
    if (!canvas) return;
    if (!conversationId) {
      setError("Выберите разговор для привязки наблюдения.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const frame = await simulatorFrameSource.capture(canvas, screen, {
        resolution,
        orientation,
        scale,
      });
      const created = await api.createVisionObservation({
        conversation_id: conversationId,
        frame_base64: frame.png_base64,
        source_label: "emulator",
        captured_at: new Date().toISOString(),
        analyze: true,
      });
      setLastObservation(created);
      logJournal(
        "emulator",
        "Кадр эмулятора отправлен в реальную Vision-цепочку",
        `${frame.width}×${frame.height}, analyze=true, ${created.analysis_pending ? "pending" : "analyzed"}`,
      );
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const conversationOptions = (conversations.data ?? []).map((item: Conversation) => ({
    value: item.id,
    label: `Диалог ${item.id.slice(0, 8)}… (${item.autonomy_mode})`,
  }));

  return (
    <>
      {error ? <Banner kind="error">{error}</Banner> : null}
      <div className="grid-2">
        <Section
          title="Виртуальный смартфон"
          description="Кадр рендерится локально и уходит в реальный POST /api/v1/vision/observations (analyze=true). Симулятор не имитирует агента."
          actions={
            <Button variant="primary" onClick={() => void sendFrame()} disabled={busy}>
              {busy ? "Отправка…" : "Снять кадр и отправить наблюдение"}
            </Button>
          }
        >
          <div className="row">
            <Select
              value={mode}
              onChange={(value) => setMode(value as ScreenMode)}
              options={SCREEN_MODES.map((item) => ({ value: item.id, label: item.label }))}
            />
            <Select
              value={orientation}
              onChange={(value) => setOrientation(value as Orientation)}
              options={ORIENTATIONS.map((item) => ({ value: item.id, label: item.label }))}
            />
            <Select
              value={resolutionId}
              onChange={setResolutionId}
              options={RESOLUTIONS.map((item) => ({ value: item.id, label: item.label }))}
            />
            <label className="row">
              <span className="muted">Масштаб</span>
              <input
                type="range"
                min={0.5}
                max={2}
                step={0.25}
                value={scale}
                onChange={(event) => setScale(Number(event.currentTarget.value))}
              />
              <span className="muted">{scale}×</span>
            </label>
          </div>
          <div className="phone-frame">
            <canvas
              ref={canvasRef}
              data-testid="emulator-canvas"
              className="phone-canvas"
              style={{ width: scene.width * scale, height: scene.height * scale }}
            />
          </div>
        </Section>

        <Section title="Привязка и результат" description="Наблюдение прикрепляется к реальному диалогу пользователя.">
          {conversations.loading ? <Loader /> : null}
          {conversations.error ? <Banner kind="error">{conversations.error}</Banner> : null}
          {!conversations.loading && conversationOptions.length === 0 ? (
            <EmptyState>Нет диалогов — создайте разговор на вкладке «Знакомства».</EmptyState>
          ) : null}
          {conversationOptions.length > 0 ? (
            <Select
              value={conversationId}
              onChange={setConversationId}
              options={[{ value: "", label: "Выберите диалог…" }, ...conversationOptions]}
            />
          ) : null}
          {lastObservation ? (
            <div className="stack">
              <div className="row">
                <Badge tone={lastObservation.analysis_pending ? "warn" : "success"}>
                  {lastObservation.analysis_pending ? "analysis_pending" : "analyzed"}
                </Badge>
                <span className="muted">
                  {lastObservation.frame_width}×{lastObservation.frame_height},{" "}
                  {lastObservation.frame_bytes} байт
                </span>
              </div>
              <div className="mono">sha256: {lastObservation.content_sha256.slice(0, 16)}…</div>
              <div>
                <span className="muted">summary: </span>
                {lastObservation.summary ?? "—"}
              </div>
              <div className="muted">
                provider: {lastObservation.provider ?? "—"} / {lastObservation.model ?? "—"}
              </div>
            </div>
          ) : (
            <EmptyState>Кадр ещё не отправлялся.</EmptyState>
          )}
          <p className="muted">
            Фаза 1A: рендер и канал. Сценарии с ожидаемыми результатами (Фаза 1B) и панель
            управления тестом (Фаза 1C) — следующими шагами по ТЗ docs/testing/emulator-lab-spec.md.
          </p>
        </Section>
      </div>
    </>
  );
}
