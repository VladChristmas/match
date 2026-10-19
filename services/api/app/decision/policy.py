"""Политика Decision Loop (Этап 23, ADR-0029).

Формальное правило выбора одного действия из нескольких возможных и определения того, когда
лучше ничего не отправлять. Бездействие — полноценный вариант. Жёсткие ограничения важнее
оценки выгоды, а неопределённость влияет на решение. Пороговые значения — предмет OQ-9.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.decision.state import AgentState

# Режимы автономности решения (раздел 4 спецификации agent-intelligence-layer).
EXECUTE = "execute"  # Выполнить
VERIFY = "verify"  # Подготовить и проверить
ESCALATE = "escalate"  # Передать пользователю
STOP = "stop"  # Остановиться

# Варианты действий (раздел 3 спецификации).
ACT_SEND = "send_message"
ACT_ASK_CLARIFY = "ask_clarifying"
ACT_WAIT = "wait"
ACT_PROPOSE_MEETING = "propose_meeting"
ACT_ESCALATE = "escalate_to_user"
ACT_NO_OP = "no_op"

AUTO_SEND = "auto_send"

# Варианты, которые можно выполнить без отдельного подтверждения (при режиме `auto_send`).
_EXECUTABLE_ACTIONS = {ACT_SEND, ACT_ASK_CLARIFY, ACT_PROPOSE_MEETING}

# Жёсткие стоп-факторы: рекомендация `trust` приостановить и предупредить.
_STOP_ACTIONS = {"warn_and_pause"}

# Чувствительные намерения: обязательства, чувства, границы — решение принимает человек.
ESCALATION_PATTERNS = (
    "ты меня любишь",
    "любишь ли ты",
    "любишь меня",
    "серьёзные отношения",
    "серьёзно ли",
    "эксклюзив",
    "только мы",
    "давай только",
    "встречаться только",
    "жениться",
    "замуж",
    "официально",
    "do you love me",
    "exclusive",
    "commitment",
    "marry me",
)

_MEETING_PATTERNS = ("встретимся", "встретиться", "увидеться", "свидан", "кофе", "meet up")
_QUESTION_MARKERS = ("?", "как ", "что ", "почему", "зачем", "где ", "когда", "кто ")

# Пороги (OQ-9): значения фиксированы для Этапа 23 и подлежат пересмотру на сценариях.
RECIPROCITY_WAIT_THRESHOLD = 0.4
UNCERTAINTY_VERIFY_THRESHOLD = 0.67

# Причины эскалации/остановки для прозрачности решения.
REASON_RISK = "risk_warn_and_pause"
REASON_SENSITIVE = "sensitive_intent"
REASON_AUTONOMY = "autonomy_requires_confirmation"
REASON_UNCERTAIN = "insufficient_context"


@dataclass(frozen=True)
class Decision:
    """Результат Decision Loop: одно действие и объяснение выбора."""

    action: str
    mode: str
    rationale: str
    confidence: float
    alternatives: list[dict] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    escalation_reason: str | None = None
    missing: list[str] = field(default_factory=list)

    @property
    def allowed_autonomously(self) -> bool:
        """Можно ли выполнять действие автономно (Выполнить) без подтверждения человека."""
        return self.mode == EXECUTE


def _contains(text: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in text for pattern in patterns)


def _looks_like_question(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _QUESTION_MARKERS)


def _candidate_scores(state: AgentState, text: str) -> list[dict]:
    """Сравнительные оценки альтернатив (не единый «магический балл», а разбор причин)."""
    scores: dict[str, float] = {
        ACT_SEND: 0.6,
        ACT_ASK_CLARIFY: 0.4,
        ACT_WAIT: 0.3,
        ACT_PROPOSE_MEETING: 0.3,
        ACT_ESCALATE: 0.2,
        ACT_NO_OP: 0.25,
    }
    if _looks_like_question(text):
        scores[ACT_SEND] += 0.05
    if state.compatibility_uncertainty is not None:
        scores[ACT_ASK_CLARIFY] += 0.3 * state.compatibility_uncertainty
    total_messages = state.inbound_count + state.outbound_count
    if total_messages >= 2 and state.reciprocity < RECIPROCITY_WAIT_THRESHOLD:
        scores[ACT_WAIT] += 0.4
    if total_messages >= 2 and state.outbound_count > state.inbound_count:
        scores[ACT_WAIT] += 0.2
    if _contains(text, _MEETING_PATTERNS):
        scores[ACT_PROPOSE_MEETING] += 0.4

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top = ranked[0][1]
    return [
        {
            "action": action,
            "score": round(score, 2),
            "rejected_because": None if score == top else "lower_score",
        }
        for action, score in ranked
    ]


def _confidence(state: AgentState) -> float:
    penalty = 0.2 if state.missing else 0.0
    return round(max(0.1, 1.0 - state.risk_confidence * 0.5 - penalty), 2)


def _evidence(state: AgentState) -> list[dict]:
    evidence: list[dict] = []
    if state.risk_category != "none":
        evidence.append(
            {
                "kind": "risk",
                "category": state.risk_category,
                "confidence": state.risk_confidence,
            }
        )
    if state.compatibility_assessment_id is not None:
        evidence.append(
            {
                "kind": "compatibility",
                "id": str(state.compatibility_assessment_id),
                "uncertainty": state.compatibility_uncertainty,
            }
        )
    evidence.append(
        {
            "kind": "history",
            "inbound": state.inbound_count,
            "outbound": state.outbound_count,
            "reciprocity": state.reciprocity,
        }
    )
    return evidence


def decide(state: AgentState, trigger_text: str | None = None) -> Decision:
    """Выбирает действие из альтернатив с учётом ограничений, риска и неопределённости."""
    text = (trigger_text or state.last_inbound_text or "").lower()
    evidence = _evidence(state)
    confidence = _confidence(state)

    # 1. Жёсткие ограничения важнее оценки выгоды.
    if state.risk_action in _STOP_ACTIONS:
        return Decision(
            action=ACT_ESCALATE,
            mode=STOP,
            rationale=(
                f"Обнаружен стоп-фактор риска ({state.risk_category}); "
                "автономная отправка запрещена независимо от прогноза."
            ),
            confidence=confidence,
            alternatives=[],
            evidence=evidence,
            escalation_reason=REASON_RISK,
            missing=state.missing,
        )

    # 2. Чувствительные темы (обязательства, чувства, границы) — решает человек.
    if _contains(text, ESCALATION_PATTERNS):
        return Decision(
            action=ACT_ESCALATE,
            mode=ESCALATE,
            rationale=(
                "Запрос касается обязательств или чувств — нужно личное решение пользователя."
            ),
            confidence=confidence,
            alternatives=_candidate_scores(state, text),
            evidence=evidence,
            escalation_reason=REASON_SENSITIVE,
            missing=state.missing,
        )

    # 3. Автономность ограничена настройкой (пауза или не `auto_send`) — подготовить и проверить.
    if state.queue_paused or state.autonomy_mode != AUTO_SEND:
        return Decision(
            action=ACT_SEND,
            mode=VERIFY,
            rationale="Автономность ограничена настройками: ответ требует подтверждения.",
            confidence=confidence,
            alternatives=_candidate_scores(state, text),
            evidence=evidence,
            escalation_reason=REASON_AUTONOMY,
            missing=state.missing,
        )

    # 4. Недостаток достоверных данных — осторожное действие вместо уверенного ответа.
    if (
        state.compatibility_uncertainty is not None
        and state.compatibility_uncertainty >= UNCERTAINTY_VERIFY_THRESHOLD
    ):
        return Decision(
            action=ACT_ASK_CLARIFY,
            mode=VERIFY,
            rationale="Мало достоверных данных о собеседнике: уточнить, а не действовать наугад.",
            confidence=confidence,
            alternatives=_candidate_scores(state, text),
            evidence=evidence,
            escalation_reason=REASON_UNCERTAIN,
            missing=state.missing,
        )

    # 5. Выбор лучшего варианта; бездействие (wait/no_op) — полноценная альтернатива.
    alternatives = _candidate_scores(state, text)
    chosen = alternatives[0]["action"]
    mode = EXECUTE if chosen in _EXECUTABLE_ACTIONS else VERIFY
    return Decision(
        action=chosen,
        mode=mode,
        rationale=_rationale_for(chosen, state),
        confidence=confidence,
        alternatives=alternatives,
        evidence=evidence,
        escalation_reason=None if mode == EXECUTE else REASON_UNCERTAIN,
        missing=state.missing,
    )


def _rationale_for(action: str, state: AgentState) -> str:
    if action == ACT_WAIT:
        return "Инициатива собеседника ниже: пауза естественнее ещё одного сообщения."
    if action == ACT_NO_OP:
        return "Сейчас действие не требуется."
    if action == ACT_PROPOSE_MEETING:
        return "В переписке есть сигнал к встрече — предложить её уместно."
    if action == ACT_ASK_CLARIFY:
        return "Есть неопределённость — уточняющий вопрос снизит риск ошибки."
    return "Обычный ответ в стиле пользователя соответствует целям и ситуации."
