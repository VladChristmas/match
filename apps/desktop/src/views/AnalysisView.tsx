import { useState } from "react";

import {
  Badge,
  Banner,
  Button,
  EmptyState,
  Field,
  JsonInput,
  Loader,
  ScoreMeter,
  Section,
  Select,
  TagInput,
  TextArea,
} from "../components/ui";
import { useApp } from "../context/AppContext";
import { errorMessage } from "../lib/api";
import { useAsyncData } from "../lib/hooks";
import type {
  CompatibilityAssessment,
  JsonObject,
  RiskAssessment,
} from "../lib/types";

function riskTone(category: string): string {
  if (category === "low" || category === "none") return "ok";
  if (category === "high" || category === "critical") return "error";
  return "warn";
}

export function AnalysisView() {
  const { api, logJournal } = useApp();
  const conversations = useAsyncData(() => api.listConversations(), [api]);
  const compatibilityHistory = useAsyncData(() => api.listCompatibility(), [api]);
  const riskHistory = useAsyncData(() => api.listRisk(), [api]);

  const [conversationId, setConversationId] = useState("");

  const [goals, setGoals] = useState<string[]>([]);
  const [values, setValues] = useState<string[]>([]);
  const [lifestyle, setLifestyle] = useState<JsonObject>({});
  const [reciprocity, setReciprocity] = useState("");
  const [compatibility, setCompatibility] = useState<CompatibilityAssessment | null>(null);
  const [compatError, setCompatError] = useState<string | null>(null);
  const [compatBusy, setCompatBusy] = useState(false);

  const [riskText, setRiskText] = useState("");
  const [risk, setRisk] = useState<RiskAssessment | null>(null);
  const [riskError, setRiskError] = useState<string | null>(null);
  const [riskBusy, setRiskBusy] = useState(false);

  const conversationOptions = [
    { value: "", label: "Без привязки к разговору" },
    ...(conversations.data ?? []).map((item) => ({
      value: item.id,
      label: item.match_id ? `match ${item.match_id.slice(0, 8)}` : `диалог ${item.id.slice(0, 8)}`,
    })),
  ];

  async function assessCompatibility() {
    setCompatBusy(true);
    setCompatError(null);
    const parsedReciprocity = reciprocity.trim() === "" ? null : Number(reciprocity);
    try {
      const result = await api.createCompatibility({
        conversation_id: conversationId || null,
        counterpart: { goals, values, lifestyle },
        reciprocity: parsedReciprocity,
      });
      setCompatibility(result);
      logJournal("compatibility", "Оценка совместимости", result.model_version);
      compatibilityHistory.reload();
    } catch (err) {
      setCompatError(errorMessage(err));
    } finally {
      setCompatBusy(false);
    }
  }

  async function assessRisk() {
    setRiskBusy(true);
    setRiskError(null);
    const messages = riskText
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean);
    try {
      const result = await api.createRisk({
        conversation_id: conversationId || null,
        messages,
      });
      setRisk(result);
      logJournal("risk", "Оценка риска", result.risk_category);
      riskHistory.reload();
    } catch (err) {
      setRiskError(errorMessage(err));
    } finally {
      setRiskBusy(false);
    }
  }

  return (
    <>
      <Section title="Контекст оценки" description="Привязка к разговору необязательна.">
        <Field label="Разговор">
          <Select value={conversationId} onChange={setConversationId} options={conversationOptions} />
        </Field>
      </Section>

      <Section
        title="Совместимость"
        description="Эвристическая оценка целей, ценностей и образа жизни собеседника."
        actions={
          <Button variant="primary" onClick={() => void assessCompatibility()} disabled={compatBusy}>
            {compatBusy ? "Оценка…" : "Оценить совместимость"}
          </Button>
        }
      >
        <Field label="Цели собеседника">
          <TagInput value={goals} onChange={setGoals} placeholder="Enter или запятая" />
        </Field>
        <Field label="Ценности собеседника">
          <TagInput value={values} onChange={setValues} placeholder="Enter или запятая" />
        </Field>
        <div className="grid-2">
          <JsonInput label="Образ жизни (JSON)" value={lifestyle} onChange={setLifestyle} />
          <Field label="Взаимность (0–1)" hint="Необязательно. Доля ответной инициативы.">
            <input
              className="input"
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={reciprocity}
              onChange={(event) => setReciprocity(event.currentTarget.value)}
            />
          </Field>
        </div>
        {compatError ? <Banner kind="error">{compatError}</Banner> : null}
        {compatibility ? (
          <div className="nested">
            <ScoreMeter label="Цели" value={compatibility.goals_alignment} />
            <ScoreMeter label="Ценности" value={compatibility.values_alignment} />
            <ScoreMeter label="Образ жизни" value={compatibility.lifestyle_alignment} />
            <ScoreMeter label="Взаимность" value={compatibility.reciprocity} />
            <ScoreMeter label="Неопределённость" value={compatibility.uncertainty} />
            {compatibility.explanation ? (
              <p className="muted">{compatibility.explanation}</p>
            ) : null}
          </div>
        ) : null}
      </Section>

      <Section
        title="Оценка риска"
        description="Сигналы риска по сообщениям. Каждая строка — отдельное сообщение."
        actions={
          <Button variant="primary" onClick={() => void assessRisk()} disabled={riskBusy}>
            {riskBusy ? "Оценка…" : "Оценить риск"}
          </Button>
        }
      >
        <TextArea value={riskText} onChange={setRiskText} rows={5} placeholder="Сообщение 1&#10;Сообщение 2" />
        {riskError ? <Banner kind="error">{riskError}</Banner> : null}
        {risk ? (
          <div className="nested">
            <div className="row">
              <Badge tone={riskTone(risk.risk_category)}>{risk.risk_category}</Badge>
              <span className="muted">Уверенность: {Math.round(risk.confidence * 100)}%</span>
              <span className="muted">Действие: {risk.recommended_action}</span>
            </div>
            {risk.signals.length > 0 ? (
              <ul className="plain-list">
                {risk.signals.map((signal) => (
                  <li key={signal.category}>
                    {signal.category}: {signal.matches}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">Сигналы не обнаружены.</p>
            )}
            {risk.explanation ? <p className="muted">{risk.explanation}</p> : null}
          </div>
        ) : null}
      </Section>

      <Section title="История оценок">
        <div className="grid-2">
          <div>
            <h3>Совместимость</h3>
            {compatibilityHistory.loading ? <Loader /> : null}
            {compatibilityHistory.data && compatibilityHistory.data.length === 0 ? (
              <EmptyState>Оценок пока нет.</EmptyState>
            ) : null}
            <ul className="plain-list">
              {compatibilityHistory.data?.map((item) => (
                <li key={item.id}>
                  {new Date(item.assessed_at).toLocaleString()} · цели{" "}
                  {Math.round(item.goals_alignment * 100)}% · ценности{" "}
                  {Math.round(item.values_alignment * 100)}%
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h3>Риск</h3>
            {riskHistory.loading ? <Loader /> : null}
            {riskHistory.data && riskHistory.data.length === 0 ? (
              <EmptyState>Оценок пока нет.</EmptyState>
            ) : null}
            <ul className="plain-list">
              {riskHistory.data?.map((item) => (
                <li key={item.id}>
                  {new Date(item.assessed_at).toLocaleString()} ·{" "}
                  <Badge tone={riskTone(item.risk_category)}>{item.risk_category}</Badge>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </Section>
    </>
  );
}
