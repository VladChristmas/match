import { Banner, Section } from "../components/ui";
import { useApp } from "../context/AppContext";
import { useAsyncData } from "../lib/hooks";
import type { AdminMetric, AdminMetrics } from "../lib/types";

const SECTIONS: { key: keyof AdminMetrics; title: string; keyLabel: string }[] = [
  { key: "users", title: "Пользователи", keyLabel: "по ролям" },
  { key: "conversations", title: "Диалоги", keyLabel: "по статусу" },
  { key: "messages", title: "Сообщения", keyLabel: "по обработке" },
  { key: "model_runs", title: "Запуски моделей", keyLabel: "по задаче" },
  { key: "model_runs_by_provider", title: "Запуски моделей (провайдер)", keyLabel: "по провайдеру" },
  { key: "vision_observations", title: "Наблюдения зрения", keyLabel: "по провайдеру" },
  { key: "agent_actions", title: "Действия агента", keyLabel: "по статусу" },
  { key: "feedback", title: "Обратная связь", keyLabel: "по типу" },
  { key: "access_tokens", title: "Токены доступа", keyLabel: "по состоянию" },
];

function MetricTable({ metric, keyLabel }: { metric: AdminMetric; keyLabel: string }) {
  const entries = Object.entries(metric.by_key ?? {}).sort((a, b) => b[1] - a[1]);
  return (
    <>
      <p>
        Всего: <strong>{metric.total}</strong>
      </p>
      {entries.length === 0 ? (
        <p className="muted">Нет данных.</p>
      ) : (
        <table className="tokens">
          <thead>
            <tr>
              <th>{keyLabel}</th>
              <th>Количество</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([key, value]) => (
              <tr key={key}>
                <td>{key}</td>
                <td>{value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}

export function AdminView() {
  const { api } = useApp();
  const metrics = useAsyncData(() => api.adminMetrics(), [api]);

  if (metrics.loading) {
    return <p className="muted">Загрузка метрик…</p>;
  }
  if (metrics.error) {
    return (
      <Banner kind="error">
        {metrics.error} Доступ к кабинету есть только у роли <code>admin</code> (список
        <code> MATCH_ADMIN_TOKEN_REFS</code> на сервере).
      </Banner>
    );
  }
  const data = metrics.data;
  if (!data) {
    return <p className="muted">Метрик нет.</p>;
  }

  return (
    <>
      <Section
        title="Сводка"
        description="Агрегированные счётчики без персональных данных (ADR-0007, ADR-0021)."
      >
        <dl className="kv">
          <dt>Обновлено</dt>
          <dd>{new Date(data.generated_at).toLocaleString("ru-RU")}</dd>
          <dt>Среда</dt>
          <dd>{data.settings.environment ?? "—"}</dd>
          <dt>LLM</dt>
          <dd>{data.settings.llm_provider ?? "—"}</dd>
          <dt>Vision</dt>
          <dd>{data.settings.vision_provider ?? "—"}</dd>
          <dt>Лимитер</dt>
          <dd>
            {data.settings.rate_limit_backend ?? "—"} (
            {data.settings.rate_limit_per_minute ?? "0"}/мин)
          </dd>
          <dt>Легаси-токены</dt>
          <dd>{data.settings.auth_allow_legacy_tokens ?? "—"}</dd>
        </dl>
      </Section>

      {SECTIONS.map((item) => (
        <Section key={item.key} title={item.title}>
          <MetricTable metric={data[item.key] as AdminMetric} keyLabel={item.keyLabel} />
        </Section>
      ))}
    </>
  );
}
