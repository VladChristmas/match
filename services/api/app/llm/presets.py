"""Пресеты бесплатных облачных провайдеров (Этап 18, OQ-2).

`MATCH_LLM_PRESET` заполняет `base_url` и модель OpenAI-совместимого провайдера,
поэтому для подключения бесплатного облака достаточно задать ключ
`MATCH_OPENAI_API_KEY`. Когда пресет выбран, явные `MATCH_OPENAI_BASE_URL` и
`MATCH_OPENAI_MODEL` игнорируются — так пользователь не может случайно собрать
полу-настроенную комбинацию. Локальный `ollama` и оффлайн `echo` пресетов не
требуют.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CloudPreset:
    name: str
    label: str
    base_url: str
    model: str


PRESETS: dict[str, CloudPreset] = {
    "groq": CloudPreset(
        name="groq",
        label="Groq (free tier)",
        base_url="https://api.groq.com/openai/v1",
        model="llama-3.3-70b-versatile",
    ),
    "gemini": CloudPreset(
        name="gemini",
        label="Google Gemini (free tier, OpenAI-compatible)",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        model="gemini-2.0-flash",
    ),
    "openrouter": CloudPreset(
        name="openrouter",
        label="OpenRouter (free models)",
        base_url="https://openrouter.ai/api/v1",
        model="meta-llama/llama-3.3-70b-instruct:free",
    ),
    "cerebras": CloudPreset(
        name="cerebras",
        label="Cerebras (free tier)",
        base_url="https://api.cerebras.ai/v1",
        model="llama-3.3-70b",
    ),
}


def resolve_preset(name: str) -> CloudPreset | None:
    """Вернуть пресет по имени или `None`, если имя пустое/неизвестно."""
    return PRESETS.get(name.strip().lower())
