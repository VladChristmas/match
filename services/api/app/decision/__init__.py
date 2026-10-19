"""Match Decision Loop — формальный выбор действия (Этап 23, ADR-0029).

Чистая политика выбора одного действия (или осознанного бездействия) из альтернатив с
объяснением. Надстройка над существующими движками; ничего не хранит и не выполняет
действия самостоятельно — решение применяет вызывающий код (`app.agent.service`).
"""

from app.decision.engine import Decision, persist_decision
from app.decision.policy import (
    ACT_ASK_CLARIFY,
    ACT_ESCALATE,
    ACT_NO_OP,
    ACT_PROPOSE_MEETING,
    ACT_SEND,
    ACT_WAIT,
    ESCALATE,
    EXECUTE,
    STOP,
    VERIFY,
    decide,
)
from app.decision.state import AgentState, build_state

__all__ = [
    "ACT_ASK_CLARIFY",
    "ACT_ESCALATE",
    "ACT_NO_OP",
    "ACT_PROPOSE_MEETING",
    "ACT_SEND",
    "ACT_WAIT",
    "AgentState",
    "Decision",
    "ESCALATE",
    "EXECUTE",
    "STOP",
    "VERIFY",
    "build_state",
    "decide",
    "persist_decision",
]
