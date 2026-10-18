import { useEffect, useState } from "react";

import { Banner, Button, Field, Section, TextInput } from "../components/ui";
import { useApp } from "../context/AppContext";
import { ApiClient, errorMessage } from "../lib/api";
import { loadAppInfo, type AppInfo } from "../lib/settings";

type Status = { kind: "success" | "error" | "info"; text: string } | null;

export function SettingsView() {
  const { settings, update, logJournal } = useApp();
  const [baseUrl, setBaseUrl] = useState(settings.apiBaseUrl);
  const [token, setToken] = useState(settings.token);
  const [info, setInfo] = useState<AppInfo | null>(null);
  const [status, setStatus] = useState<Status>(null);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    void loadAppInfo().then(setInfo);
  }, []);

  function save() {
    update({ apiBaseUrl: baseUrl.trim(), token: token.trim() });
    logJournal("settings", "Настройки подключения обновлены", baseUrl.trim());
    setStatus({ kind: "success", text: "Настройки сохранены." });
  }

  async function test() {
    setTesting(true);
    setStatus({ kind: "info", text: "Проверяем соединение…" });
    const probe = new ApiClient({ baseUrl: baseUrl.trim(), token: token.trim() });
    try {
      const health = await probe.health();
      const ready = await probe.ready();
      const database = (ready as { database?: unknown }).database;
      setStatus({
        kind: "success",
        text: `API: ${health.status}. База данных: ${String(database ?? "ok")}.`,
      });
    } catch (err) {
      setStatus({ kind: "error", text: errorMessage(err) });
    } finally {
      setTesting(false);
    }
  }

  return (
    <>
      <Section
        title="Подключение к серверу"
        description="Адрес FastAPI-сервиса и токен доступа. Токен идентифицирует пользователя (ADR-0010)."
      >
        <div className="grid-2">
          <Field label="Адрес API" hint="Например, http://127.0.0.1:8000">
            <TextInput value={baseUrl} onChange={setBaseUrl} placeholder="http://127.0.0.1:8000" />
          </Field>
          <Field
            label="Токен доступа"
            hint="Передаётся как Authorization: Bearer. Персональные данные не собираются."
          >
            <TextInput value={token} onChange={setToken} placeholder="match-token-…" />
          </Field>
        </div>
        <div className="row">
          <Button variant="primary" onClick={save}>
            Сохранить
          </Button>
          <Button onClick={() => void test()} disabled={testing}>
            {testing ? "Проверка…" : "Проверить соединение"}
          </Button>
        </div>
        {status ? <Banner kind={status.kind}>{status.text}</Banner> : null}
        <Banner kind="warn">
          Токен хранится локально на этом устройстве. Не используйте чужие токены и не передавайте их
          третьим лицам.
        </Banner>
      </Section>

      <Section title="О приложении">
        {info ? (
          <dl className="kv">
            <dt>Название</dt>
            <dd>{info.name}</dd>
            <dt>Версия</dt>
            <dd>{info.version}</dd>
            <dt>Tauri</dt>
            <dd>{info.tauri_version}</dd>
            <dt>ОС</dt>
            <dd>{info.os}</dd>
          </dl>
        ) : (
          <p className="muted">
            Приложение запущено в браузере (режим разработки). Настройки сохраняются в локальном
            хранилище браузера.
          </p>
        )}
      </Section>
    </>
  );
}
