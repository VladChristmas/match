import { useCallback, useEffect, useState } from "react";

import {
  Banner,
  Button,
  Field,
  JsonInput,
  Loader,
  Section,
  Select,
  TagInput,
} from "../components/ui";
import { useApp } from "../context/AppContext";
import { errorMessage } from "../lib/api";
import type {
  CommunicationProfile,
  JsonObject,
  UserProfile,
} from "../lib/types";

const LENGTH_OPTIONS = [
  { value: "", label: "Не задано" },
  { value: "short", label: "Короткие сообщения" },
  { value: "medium", label: "Средние сообщения" },
  { value: "long", label: "Развёрнутые сообщения" },
];

export function ProfileView() {
  const { api, logJournal } = useApp();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [goals, setGoals] = useState<string[]>([]);
  const [values, setValues] = useState<string[]>([]);
  const [preferences, setPreferences] = useState<JsonObject>({});
  const [boundaries, setBoundaries] = useState<JsonObject>({});

  const [comm, setComm] = useState<CommunicationProfile | null>(null);
  const [length, setLength] = useState("");
  const [style, setStyle] = useState<JsonObject>({});
  const [tone, setTone] = useState<JsonObject>({});
  const [humor, setHumor] = useState<JsonObject>({});
  const [initiative, setInitiative] = useState<JsonObject>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [p, c] = await Promise.all([api.getProfile(), api.getCommunication()]);
      setProfile(p);
      setGoals(p.relationship_goals);
      setValues(p.values);
      setPreferences(p.preferences);
      setBoundaries(p.boundaries);
      setComm(c);
      setLength(c.typical_message_length ?? "");
      setStyle(c.style_preferences);
      setTone(c.tone_preferences);
      setHumor(c.humor_preferences);
      setInitiative(c.initiative_preferences);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    void load();
  }, [load]);

  async function saveProfile() {
    setBusy(true);
    setNotice(null);
    try {
      const updated = await api.updateProfile({
        relationship_goals: goals,
        values,
        preferences,
        boundaries,
      });
      setProfile(updated);
      logJournal("profile", "Профиль сохранён", `Версия ${updated.profile_version}`);
      setNotice("Профиль сохранён.");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function saveCommunication() {
    setBusy(true);
    setNotice(null);
    try {
      const updated = await api.updateCommunication({
        style_preferences: style,
        tone_preferences: tone,
        typical_message_length: length === "" ? null : length,
        humor_preferences: humor,
        initiative_preferences: initiative,
      });
      setComm(updated);
      logJournal("communication", "Профиль общения сохранён", `Версия ${updated.version}`);
      setNotice("Профиль общения сохранён.");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <Loader label="Загружаем профиль…" />;

  return (
    <>
      {error ? <Banner kind="error">{error}</Banner> : null}
      {notice ? <Banner kind="success">{notice}</Banner> : null}

      <Section
        title="Профиль пользователя"
        description="Цели, ценности и границы. Используются для оценки совместимости и доверия."
        actions={
          <Button variant="primary" onClick={() => void saveProfile()} disabled={busy}>
            Сохранить профиль
          </Button>
        }
      >
        <Field label="Цели в отношениях" hint="Enter или запятая — добавить. Значения — теги.">
          <TagInput value={goals} onChange={setGoals} placeholder="Например: долгосрочные отношения" />
        </Field>
        <Field label="Ценности">
          <TagInput value={values} onChange={setValues} placeholder="Например: честность" />
        </Field>
        <div className="grid-2">
          <JsonInput
            key={`prefs-${profile?.profile_version ?? 0}`}
            label="Предпочтения (JSON)"
            value={preferences}
            onChange={setPreferences}
          />
          <JsonInput
            key={`bounds-${profile?.profile_version ?? 0}`}
            label="Границы (JSON)"
            value={boundaries}
            onChange={setBoundaries}
          />
        </div>
        {profile ? (
          <p className="muted">
            Версия профиля: {profile.profile_version} · обновлён{" "}
            {new Date(profile.updated_at).toLocaleString()}
          </p>
        ) : null}
      </Section>

      <Section
        title="Профиль общения"
        description="Как агент пишет от имени пользователя. Психопрофиль собеседника видит только пользователь."
        actions={
          <Button variant="primary" onClick={() => void saveCommunication()} disabled={busy}>
            Сохранить стиль
          </Button>
        }
      >
        <div className="grid-2">
          <Field label="Типичная длина сообщения">
            <Select value={length} onChange={setLength} options={LENGTH_OPTIONS} />
          </Field>
          <div />
        </div>
        <div className="grid-2">
          <JsonInput
            key={`style-${comm?.version ?? 0}`}
            label="Стиль (JSON)"
            value={style}
            onChange={setStyle}
          />
          <JsonInput
            key={`tone-${comm?.version ?? 0}`}
            label="Тон (JSON)"
            value={tone}
            onChange={setTone}
          />
        </div>
        <div className="grid-2">
          <JsonInput
            key={`humor-${comm?.version ?? 0}`}
            label="Юмор (JSON)"
            value={humor}
            onChange={setHumor}
          />
          <JsonInput
            key={`init-${comm?.version ?? 0}`}
            label="Инициатива (JSON)"
            value={initiative}
            onChange={setInitiative}
          />
        </div>
        {comm ? (
          <p className="muted">
            Версия стиля: {comm.version} · обновлён {new Date(comm.updated_at).toLocaleString()}
          </p>
        ) : null}
      </Section>
    </>
  );
}
