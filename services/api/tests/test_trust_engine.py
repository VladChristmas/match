from app.trust.engine import assess_risk


def test_no_signals_returns_none():
    result = assess_risk(["Привет, как дела?"])
    assert result.risk_category == "none"
    assert result.signals == []
    assert result.confidence == 0.0
    assert result.recommended_action == "none"


def test_financial_and_urgency_detected():
    result = assess_risk(["Срочно переведи деньги на биткоин кошелёк"])
    categories = {signal.category for signal in result.signals}
    assert "financial_request" in categories
    assert "urgency_pressure" in categories
    assert result.risk_category == "financial_request"
    assert result.recommended_action == "warn_and_pause"
    assert result.confidence > 0.9


def test_isolation_only():
    result = assess_risk(["Никому не говори об этом, только между нами"])
    assert result.risk_category == "isolation"
    assert result.recommended_action == "warn_user"
