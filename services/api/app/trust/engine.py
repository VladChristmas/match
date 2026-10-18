from dataclasses import dataclass

RISK_RULES: dict[str, tuple[str, ...]] = {
    "financial_request": (
        "переведи деньги",
        "перевести деньги",
        "кошел",
        "биткоин",
        "крипт",
        "money",
        "crypto",
        "bitcoin",
        "western union",
        "gift card",
        "реквизит",
    ),
    "personal_data_request": (
        "номер карты",
        "cvv",
        "паспорт",
        "код из смс",
        "код подтверждения",
        "card number",
    ),
    "isolation": (
        "никому не говори",
        "не рассказывай",
        "только между нами",
        "держи в секрете",
        "keep it secret",
        "don't tell anyone",
    ),
    "urgency_pressure": (
        "срочно",
        "немедленно",
        "прямо сейчас",
        "asap",
        "urgent",
        "right now",
    ),
}

SEVERITY: dict[str, float] = {
    "financial_request": 0.9,
    "personal_data_request": 0.85,
    "isolation": 0.7,
    "urgency_pressure": 0.5,
}

RECOMMENDED_ACTION: dict[str, str] = {
    "financial_request": "warn_and_pause",
    "personal_data_request": "warn_and_pause",
    "isolation": "warn_user",
    "urgency_pressure": "observe",
}


@dataclass(frozen=True)
class RiskSignal:
    category: str
    matches: int


@dataclass(frozen=True)
class RiskResult:
    risk_category: str
    signals: list[RiskSignal]
    confidence: float
    explanation: str
    recommended_action: str


def assess_risk(messages: list[str]) -> RiskResult:
    combined = "\n".join(messages).lower()
    signals = [
        RiskSignal(category=category, matches=sum(combined.count(k) for k in keywords))
        for category, keywords in RISK_RULES.items()
    ]
    signals = [signal for signal in signals if signal.matches]
    if not signals:
        return RiskResult(
            risk_category="none",
            signals=[],
            confidence=0.0,
            explanation="No risk signals detected.",
            recommended_action="none",
        )
    top = max(signals, key=lambda signal: SEVERITY[signal.category])
    confidence = min(1.0, SEVERITY[top.category] + 0.05 * (len(signals) - 1))
    categories = ", ".join(signal.category for signal in signals)
    return RiskResult(
        risk_category=top.category,
        signals=signals,
        confidence=round(confidence, 2),
        explanation=f"Detected risk signals: {categories}.",
        recommended_action=RECOMMENDED_ACTION[top.category],
    )
