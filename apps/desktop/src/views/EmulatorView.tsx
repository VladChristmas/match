import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";

import { Badge, Banner, Button, EmptyState, Loader, Section, Select } from "../components/ui";
import { useApp } from "../context/AppContext";
import { errorMessage } from "../lib/api";
import { simulatorFrameSource } from "../lib/emulator/frameSource";
import { createScenarioRunner } from "../lib/emulator/runner";
import { SCENARIOS } from "../lib/emulator/scenarios";
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
import type { AgentAction, AgentDecision, AutonomyErrorLog, Conversation, VisionObservation } from "../lib/types";

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

const STATUS_LABEL: Record<string, string> = {
  idle: "Готов",
  running: "Выполняется",
  paused: "Пауза",
  done: "Завершён",
  failed: "Провал",
};

export function EmulatorView() {
  const { api, logJournal } = useApp();
  const conversations = useAsyncData(() => api.listConversations(), [api]);

  const [mode, setMode] = useState<ScreenMode>("chat");
  const [orientation, setOrientation] = useState<Orientation>("portrait");
  const [resolutionId, setResolutionId] = useState(RESOLUTIONS[0].id);
  const [scale, setScale] = useState(1);
  const [scenarioId, setScenarioId] = useState(SCENARIOS[0].id);
  const [conversationId, setConversationId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastObservation, setLastObservation] = useState<VisionObservation | null>(null);
  const [liveNonce, setLiveNonce] = useState(0);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const screen: VirtualScreen = DEMO_SCREENS[mode];
  const resolution = findResolution(resolutionId);
  const scene = buildScene(screen, { resolution, orientation });

  const selectedScenario = useMemo(
    () => SCENARIOS.find((item) => item.id === scenarioId) ?? SCENARIOS[0],
    [scenarioId],
  );

  const onStepResult = useCallback((result: { step_id: string }) => {
    const step = selectedScenario.steps.find((item) => item.id === result.step_id);
    if (step?.kind === "show_screen" && step.payload && "screen" in step.payload) {
      const next = step.payload.screen as VirtualScreen;
      setMode(next.mode);
    }
    setLiveNonce((value) => value + 1);
  }, [selectedScenario]);

  const runner = useMemo(
    () =>
      createScenarioRunner({
        api,
        frameSource: simulatorFrameSource,
        getCanvas: () => canvasRef.current,
        getRenderOptions: () => ({ resolutionId, orientation, scale }),
        onResult: onStepResult,
        onStatus: (status) => {
          if (status === "done") logJournal("emulator", "Сценарий завершён", selectedScenario.id);
        },
      }),
    // api и колбэки стабильны; renderOptions читаются живьём через getRenderOptions.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [api, onStepResult, selectedScenario.id],
  );

  const snapshot = useSyncExternalStore(runner.subscribe, runner.getSnapshot);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    canvas.width = scene.width;
    canvas.height = scene.height;
    paint(ctx, scene, scale);
  }, [scene, scale]);

  const actions = useAsyncData(() => api.listActions(undefined, 50), [api, liveNonce]);
  const decisions = useAsyncData(() => api.listDecisions(undefined, 50), [api, liveNonce]);
  const budget = useAsyncData(() => api.getAutonomyBudget(), [api, liveNonce]);
  const autonomyErrors = useAsyncData(() => api.listAutonomyErrors(50), [api, liveNonce]);

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
      const frame = await simulatorFrameSource.capture(canvas, screen, { resolution, orientation, scale });
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

  function startScenario() {
    setError(null);
    void runner.run(selectedScenario);
  }

  const conversationOptions = (conversations.data ?? []).map((item: Conversation) => ({
    value: item.id,
    label: `Диалог ${item.id.slice(0, 8)}… (${item.autonomy_mode})`,
  }));

  const failedCount = snapshot.results.filter((item) => !item.ok).length;

  return (
    <>
      {error ? <Banner kind="error">{error}</Banner> : null}
      {snapshot.runError ? <Banner kind="error">Сценарий: {snapshot.runError}</Banner> : null}
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

        <Section title="Управление тестом" description="Сценарии — данные (ТЗ §4); прогнан через реальные endpoint'ы агента.">
          <div className="row">
            <Select
              value={scenarioId}
              onChange={setScenarioId}
              options={SCENARIOS.map((item) => ({ value: item.id, label: item.title }))}
            />
            <Badge tone={snapshot.status === "failed" ? "error" : snapshot.status === "done" ? "success" : "neutral"}>
              {STATUS_LABEL[snapshot.status] ?? snapshot.status}
            </Badge>
          </div>
          <div className="row">
            <Button
              variant="primary"
              onClick={startScenario}
              disabled={snapshot.status === "running" || snapshot.status === "paused"}
            >
              Запустить сценарий
            </Button>
            <Button onClick={() => runner.pause()} disabled={snapshot.status !== "running"}>
              Пауза
            </Button>
            <Button onClick={() => runner.resume()} disabled={snapshot.status !== "paused"}>
              Продолжить
            </Button>
            <Button onClick={() => runner.reset()} disabled={snapshot.status === "idle"}>
              Сбросить
            </Button>
          </div>
          <p className="muted">
            Шагов: {selectedScenario.steps.length}, seed-диалогов: {selectedScenario.seed.length}.
            Idempotency-Key детерминирован (match-emu-{'{'}сценарий{'}'}-{'{'}шаг{'}'}) — повтор
            доказывает отсутствие дублей.
          </p>

          <h3>Привязка (для ручной отправки кадра)</h3>
          {conversationOptions.length > 0 ? (
            <Select
              value={conversationId}
              onChange={setConversationId}
              options={[{ value: "", label: "Выберите диалог…" }, ...conversationOptions]}
            />
          ) : (
            <EmptyState>Нет диалогов — создайте разговор на вкладке «Знакомства».</EmptyState>
          )}
          {lastObservation ? (
            <div className="stack">
              <div className="row">
                <Badge tone={lastObservation.analysis_pending ? "warn" : "success"}>
                  {lastObservation.analysis_pending ? "analysis_pending" : "analyzed"}
                </Badge>
                <span className="muted">
                  {lastObservation.frame_width}×{lastObservation.frame_height}, {lastObservation.frame_bytes} байт
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
          ) : null}
        </Section>
      </div>

      <Section
        title="Результат сценария"
        description="Ожидаемый и фактический результат каждого шага, время ответа, ошибки, повторы."
        actions={
          snapshot.results.length > 0 ? (
            <span className="muted">
              шагов: {snapshot.results.length}, провалов: {failedCount}
            </span>
          ) : null
        }
      >
        {snapshot.results.length === 0 ? (
          <EmptyState>Сценарий ещё не запускался.</EmptyState>
        ) : (
          <table className="tokens">
            <thead>
              <tr>
                <th>Шаг</th>
                <th>Ожидалось</th>
                <th>Факт</th>
                <th>HTTP</th>
                <th>Время</th>
                <th>Итог</th>
              </tr>
            </thead>
            <tbody>
              {snapshot.results.map((item) => (
                <tr key={item.step_id}>
                  <td>
                    {item.title}
                    {item.error ? <div className="field-error">{item.error}</div> : null}
                    {item.duplicate ? <div className="muted">повтор по ключу (200, то же действие)</div> : null}
                  </td>
                  <td>{item.expected}</td>
                  <td>{item.actual}</td>
                  <td>{item.http_status ?? "—"}</td>
                  <td>{item.duration_ms} мс</td>
                  <td>
                    <Badge tone={item.ok ? "success" : "error"}>{item.ok ? "ok" : "FAIL"}</Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {snapshot.results.length > 0 && failedCount > 0 ? (
          <Button variant="primary" onClick={startScenario} disabled={snapshot.status === "running" || snapshot.status === "paused"}>
            Повторить сценарий
          </Button>
        ) : null}
      </Section>

      <div className="grid-2">
        <Section title="Действия агента (live)" description="Список действий очереди — источник истины.">
          {actions.loading ? <Loader /> : null}
          {(actions.data ?? []).length === 0 && !actions.loading ? <EmptyState>Действий нет.</EmptyState> : null}
          {(actions.data ?? []).slice(0, 8).map((item: AgentAction) => (
            <div className="row" key={item.id}>
              <Badge tone={item.status === "sent" ? "success" : item.status === "pending" ? "warn" : "neutral"}>
                {item.status}
              </Badge>
              <span className="mono">{item.id.slice(0, 8)}…</span>
              <span className="muted">{item.text?.slice(0, 60) ?? "—"}</span>
            </div>
          ))}
        </Section>

        <Section title="Решения агента (live)" description="Decision Loop: режим и причина эскалации/остановки.">
          {decisions.loading ? <Loader /> : null}
          {(decisions.data ?? []).length === 0 && !decisions.loading ? <EmptyState>Решений нет.</EmptyState> : null}
          {(decisions.data ?? []).slice(0, 8).map((item: AgentDecision) => (
            <div className="stack" key={item.id}>
              <div className="row">
                <Badge tone="info">{item.mode}</Badge>
                <span className="muted">{item.action}</span>
                {item.escalation_reason ? <span className="field-error">{item.escalation_reason}</span> : null}
              </div>
              <div className="muted">{item.rationale}</div>
            </div>
          ))}
        </Section>

        <Section title="Бюджет автономности (live)">
          {budget.data ? (
            <div className="stack">
              <div className="row">
                <Badge tone={budget.data.global_paused ? "error" : "success"}>
                  {budget.data.global_paused ? "global_paused" : "active"}
                </Badge>
                <span className="muted">
                  дневной лимит: {budget.data.max_messages_per_day}, ошибки: {budget.data.consecutive_errors}
                </span>
              </div>
              <div className="muted">
                часы: {budget.data.active_start_hour}–{budget.data.active_end_hour}
              </div>
            </div>
          ) : (
            <Loader />
          )}
        </Section>

        <Section title="Ошибки автономности (live)">
          {(autonomyErrors.data ?? []).length === 0 && !autonomyErrors.loading ? (
            <EmptyState>Ошибок нет.</EmptyState>
          ) : null}
          {(autonomyErrors.data ?? [])
            .slice(0, 8)
            .map((item: AutonomyErrorLog) => (
              <div className="row" key={item.id}>
                <Badge tone="warn">{item.error_type}</Badge>
                <span className="muted">{new Date(item.created_at).toLocaleString("ru-RU")}</span>
              </div>
            ))}
        </Section>
      </div>
    </>
  );
}
