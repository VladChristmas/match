import { useEffect, useState } from "react";

import { Badge, Banner, Button, Field, Section, TextInput } from "../components/ui";
import { useApp } from "../context/AppContext";
import { ApiClient, errorMessage } from "../lib/api";
import { useAsyncData } from "../lib/hooks";
import { summarizeLLMStatus } from "../lib/llmStatus";
import { loadAppInfo, type AppInfo } from "../lib/settings";
import { loadStorageInfo, storageSupported, type StorageInfo } from "../lib/storage";
import type { AccessTokenIssued, LLMStatus } from "../lib/types";

type Status = { kind: "success" | "error" | "info"; text: string } | null;

const DATE_FORMAT = new Intl.DateTimeFormat("ru-RU", {
  dateStyle: "short",
  timeStyle: "short",
});

function formatMoment(value: string | null): string {
  return value ? DATE_FORMAT.format(new Date(value)) : "—";
}

function TokensSection() {
  const { api, update, logJournal } = useApp();
  const tokens = useAsyncData(() => api.listTokens(), [api]);
  const [label, setLabel] = useState("");
  const [issued, setIssued] = useState<AccessTokenIssued | null>(null);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<Status>(null);

  async function run(action: () => Promise<void>, message: string) {
    setBusy(true);
    setStatus(null);
    try {
      await action();
      setStatus({ kind: "success", text: message });
      tokens.reload();
    } catch (err) {
      setStatus({ kind: "error", text: errorMessage(err) });
    } finally {
      setBusy(false);
    }
  }

  function issue() {
    void run(async () => {
      const created = await api.issueToken(label.trim());
      setIssued(created);
      setLabel("");
      logJournal("settings", "Выдан токен доступа", created.label);
    }, "Токен создан. Сохраните его — он показывается один раз.");
  }

  function rotate(id: string) {
    void run(async () => {
      const created = await api.rotateToken(id);
      setIssued(created);
      logJournal("settings", "Токен ротирован", created.label);
    }, "Токен ротирован: старый отозван, выдана новая пара.");
  }

  function revoke(id: string) {
    void run(async () => {
      await api.revokeToken(id);
      logJournal("settings", "Токен отозван", id);
    }, "Токен отозван.");
  }

  function applyIssued() {
    if (!issued) return;
    update({ token: issued.token });
    logJournal("settings", "Активный токен обновлён", issued.label);
    setStatus({
      kind: "success",
      text: "Токен записан в настройки. Нажмите «Сохранить» выше, чтобы применить.",
    });
  }

  return (
    <Section
      title="Токены доступа"
      description="Токены выдаются сервером, хранятся в виде SHA-256 хэша и могут быть отозваны или ротированы (ADR-0019)."
    >
      <div className="row">
        <Field label="Метка токена" hint="Например, «ноутбук» или «телефон»">
          <TextInput value={label} onChange={setLabel} placeholder="устройство" />
        </Field>
        <Button variant="primary" onClick={issue} disabled={busy}>
          Создать токен
        </Button>
        <Button onClick={tokens.reload} disabled={busy || tokens.loading}>
          Обновить список
        </Button>
      </div>

      {issued ? (
        <>
          <Banner kind="warn">
            Скопируйте токен сейчас — повторно он не отображается.
          </Banner>
          <code className="token-value">{issued.token}</code>
          <div className="row">
            <Button variant="primary" onClick={applyIssued}>
              Использовать этот токен
            </Button>
            <Button onClick={() => setIssued(null)}>Скрыть</Button>
          </div>
        </>
      ) : null}

      {tokens.error ? <Banner kind="error">{tokens.error}</Banner> : null}
      {tokens.loading ? (
        <p className="muted">Загрузка токенов…</p>
      ) : (
        <table className="tokens">
          <thead>
            <tr>
              <th>Метка</th>
              <th>Создан</th>
              <th>Последнее использование</th>
              <th>Статус</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {(tokens.data ?? []).map((item) => (
              <tr key={item.id}>
                <td>{item.label || "без метки"}</td>
                <td>{formatMoment(item.created_at)}</td>
                <td>{formatMoment(item.last_used_at)}</td>
                <td>{item.revoked_at ? "отозван" : "активен"}</td>
                <td className="row">
                  <Button
                    onClick={() => rotate(item.id)}
                    disabled={busy || item.revoked_at !== null}
                  >
                    Ротировать
                  </Button>
                  <Button
                    onClick={() => revoke(item.id)}
                    disabled={busy || item.revoked_at !== null}
                  >
                    Отозвать
                  </Button>
                </td>
              </tr>
            ))}
            {(tokens.data ?? []).length === 0 ? (
              <tr>
                <td colSpan={5} className="muted">
                  Токенов пока нет.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      )}
      {status ? <Banner kind={status.kind}>{status.text}</Banner> : null}
    </Section>
  );
}

function LLMStatusSection() {
  const { api } = useApp();
  const status = useAsyncData<LLMStatus | null>(
    async () => {
      try {
        return await api.llmStatus();
      } catch {
        return null;
      }
    },
    [api],
  );

  return (
    <Section
      title="Языковая модель"
      description="Фактический провайдер ответов, резерв и лимит расхода. Проверяйте при смене настроек сервера (аудит P1-1)."
    >
      {status.loading ? <p className="muted">Загрузка статуса модели…</p> : null}
      {status.data ? (
        (() => {
          const summary = summarizeLLMStatus(status.data);
          return (
            <>
              <div className="row">
                <Badge tone={summary.tone === "ok" ? "ok" : "warn"}>{summary.headline}</Badge>
                <Badge>{summary.limitText}</Badge>
              </div>
              {summary.warnings.map((warning) => (
                <Banner kind="warn" key={warning}>
                  {warning}
                </Banner>
              ))}
            </>
          );
        })()
      ) : null}
      {!status.loading && !status.data ? (
        <Banner kind="info">
          Статус модели недоступен: проверьте адрес API и токен — сервер должен отвечать на
          GET /api/v1/llm/status.
        </Banner>
      ) : null}
    </Section>
  );
}

export function SettingsView() {
  const { settings, update, logJournal, outboxCount, syncOutbox } = useApp();
  const [baseUrl, setBaseUrl] = useState(settings.apiBaseUrl);
  const [token, setToken] = useState(settings.token);
  const [info, setInfo] = useState<AppInfo | null>(null);
  const [storage, setStorage] = useState<StorageInfo | null>(null);
  const [status, setStatus] = useState<Status>(null);
  const [testing, setTesting] = useState(false);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    void loadAppInfo().then(setInfo);
    void loadStorageInfo().then(setStorage);
  }, []);

  async function sync() {
    setSyncing(true);
    setStatus({ kind: "info", text: "Синхронизация очереди…" });
    try {
      const result = await syncOutbox();
      setStatus({
        kind: "success",
        text: `Очередь: отправлено ${result.sent}, отклонено ${result.dropped}, осталось ${result.remaining}.`,
      });
      void loadStorageInfo().then(setStorage);
    } catch (err) {
      setStatus({ kind: "error", text: errorMessage(err) });
    } finally {
      setSyncing(false);
    }
  }

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
            hint="Передаётся как Authorization: Bearer. Переписка и профиль могут содержать личные сведения — см. политику приватности."
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

      <TokensSection />

      <LLMStatusSection />

      <Section
        title="Локальное хранилище"
        description="Настройки и журнал хранятся на устройстве в SQLite (ADR-0022). На сервер они не отправляются."
      >
        {storageSupported() && storage ? (
          <dl className="kv">
            <dt>Файл</dt>
            <dd>
              <code>{storage.path}</code>
            </dd>
            <dt>SQLite</dt>
            <dd>{storage.sqlite_version}</dd>
            <dt>Версия схемы</dt>
            <dd>{storage.schema_version}</dd>
            <dt>Записей журнала</dt>
            <dd>{storage.journal_entries}</dd>
            <dt>Размер</dt>
            <dd>{Math.max(1, Math.round(storage.size_bytes / 1024))} КБ</dd>
            <dt>Настройки</dt>
            <dd>{storage.settings_present ? "сохранены" : "по умолчанию"}</dd>
          </dl>
        ) : (
          <Banner kind="info">
            Приложение запущено в браузере (режим разработки) — используется localStorage вместо
            SQLite. Локальная БД работает в desktop-сборке Tauri.
          </Banner>
        )}

        <p className="muted">
          Оффлайн-очередь: запросы, не ушедшие при отсутствии связи, сохраняются на устройстве и
          повторяются автоматически (ADR-0026).
        </p>
        <div className="row">
          <Badge tone={outboxCount > 0 ? "warn" : "ok"}>{outboxCount} в очереди</Badge>
          <Button onClick={() => void sync()} disabled={syncing || !storageSupported()}>
            {syncing ? "Синхронизация…" : "Синхронизировать"}
          </Button>
        </div>
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
