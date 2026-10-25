import re
from dataclasses import dataclass

from app.dialogue.style import StyleProfile

SYSTEM_LEAK_PATTERNS = (
    re.compile(r"as an ai", re.IGNORECASE),
    re.compile(r"system prompt", re.IGNORECASE),
    re.compile(r"<\|.*?\|>"),
    re.compile(r"user communication style", re.IGNORECASE),
    # Маркеры fencing недоверенных данных: черновик не должен их воспроизводить.
    re.compile(r"<<<"),
)


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    issues: list[str]


def validate_draft(text: str, style: StyleProfile) -> ValidationResult:
    issues: list[str] = []
    stripped = text.strip()
    if not stripped:
        issues.append("empty")
        return ValidationResult(ok=False, issues=issues)
    if len(stripped) > style.max_length:
        issues.append("too_long")
    if len(stripped) < style.min_length:
        issues.append("too_short")
    if any(pattern.search(stripped) for pattern in SYSTEM_LEAK_PATTERNS):
        issues.append("system_leak")
    return ValidationResult(ok=not issues, issues=issues)
