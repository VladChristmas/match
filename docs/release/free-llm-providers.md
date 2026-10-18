# Бесплатные облачные LLM (OQ-2)

Документ фиксирует выбор провайдеров, порядок маршрутизации и политику лимитов
(закрывает OQ-2, ADR-0024). Облако — **opt-in**: без ключа `MATCH_OPENAI_API_KEY`
провайдер `openai` пропускается, и используется локальный `ollama` или оффлайн `echo`.

## Порядок провайдеров

```
MATCH_LLM_PROVIDER=openai,ollama,echo
MATCH_LLM_FALLBACK_PROVIDERS=ollama,echo
```

- `openai` — любой OpenAI-совместимый облачный free-провайдер (ключ обязателен).
- `ollama` — локальная модель (fallback без интернета, данные не покидают машину).
- `echo` — оффлайн-заглушка (разработка и тесты).

`LLMGateway` идёт по списку и переходит к следующему провайдеру при ошибке или
пустом ответе; если не сработал никто — `LLMUnavailable` (HTTP 503).

## Пресеты

Вместо `base_url`/`model` достаточно задать пресет — он подставит endpoint и модель:

| `MATCH_LLM_PRESET` | Провайдер | Endpoint | Модель по умолчанию |
|---|---|---|---|
| `groq` | Groq (free tier) | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` |
| `gemini` | Google Gemini (free tier) | `.../v1beta/openai` | `gemini-2.0-flash` |
| `openrouter` | OpenRouter (free models) | `https://openrouter.ai/api/v1` | `meta-llama/llama-3.3-70b-instruct:free` |
| `cerebras` | Cerebras (free tier) | `https://api.cerebras.ai/v1` | `llama-3.3-70b` |

Пример `.env` (Groq):

```
MATCH_LLM_PROVIDER=openai,ollama,echo
MATCH_LLM_FALLBACK_PROVIDERS=ollama,echo
MATCH_LLM_PRESET=groq
MATCH_OPENAI_API_KEY=<ключ из личного кабинета провайдера>
```

Пресет имеет приоритет над `MATCH_OPENAI_BASE_URL`/`MATCH_OPENAI_MODEL`; без
пресета используются эти поля (любой OpenAI-совместимый endpoint).

## Политика лимитов

- `MATCH_LLM_USER_REQUEST_LIMIT` — максимум запросов к моделям на пользователя
  (0 = без ограничения). Считаются все задач (`ModelRun`), включая vision-анализ.
  Рекомендуется задавать лимит, сопоставимый с бесплатной квотой провайдера
  (например, 50–100 на пользователя в сутки — см. условия провайдера).
- `MATCH_LLM_TIMEOUT_SECONDS` (по умолчанию 30 с) — таймаут запроса; при таймауте
  срабатывает fallback на `ollama`.
- `MATCH_RATE_LIMIT_PER_MINUTE` (Этап 9/14) — защита от всплесков на `/drafts`
  и `/agent/actions`; для multi-instance используйте `MATCH_RATE_LIMIT_BACKEND=db`.

## Приватность

Облачный провайдер получает текст диалога и системный промпт. Персональные данные
не собираются (ADR-0007), но при работе с облаком стоит предупредить пользователя.
Локальный `ollama` и vision по умолчанию (`qwen3.5:9b`) остаются на устройстве.
