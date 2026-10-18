from dataclasses import dataclass, field


@dataclass(frozen=True)
class CounterpartProfile:
    goals: list[str] = field(default_factory=list)
    values: list[str] = field(default_factory=list)
    lifestyle: dict = field(default_factory=dict)


@dataclass(frozen=True)
class CompatibilityResult:
    goals_alignment: float
    values_alignment: float
    lifestyle_alignment: float
    reciprocity: float
    uncertainty: float
    explanation: str


def _jaccard(first: list[str], second: list[str]) -> float:
    set_a = {item.strip().lower() for item in first if item and item.strip()}
    set_b = {item.strip().lower() for item in second if item and item.strip()}
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


def _mapping_alignment(first: dict, second: dict) -> float:
    keys = set(first) | set(second)
    if not keys:
        return 0.0
    matches = sum(1 for key in keys if first.get(key) == second.get(key))
    return matches / len(keys)


def reciprocity_from_counts(inbound: int, outbound: int) -> float:
    total = inbound + outbound
    if total == 0:
        return 0.5
    return round(1 - abs(inbound - outbound) / total, 2)


def assess_compatibility(
    user_goals: list[str],
    user_values: list[str],
    user_preferences: dict,
    counterpart: CounterpartProfile,
    reciprocity: float | None = None,
) -> CompatibilityResult:
    goals = _jaccard(user_goals, counterpart.goals)
    values = _jaccard(user_values, counterpart.values)
    lifestyle = _mapping_alignment(user_preferences or {}, counterpart.lifestyle or {})
    reciprocity_score = 0.5 if reciprocity is None else max(0.0, min(1.0, reciprocity))
    known = sum(
        1
        for dimension in (counterpart.goals, counterpart.values, counterpart.lifestyle)
        if dimension
    )
    uncertainty = round(1 - known / 3, 2)
    explanation = (
        f"goals={goals:.2f}, values={values:.2f}, lifestyle={lifestyle:.2f}; "
        f"based on {known}/3 counterpart dimensions."
    )
    return CompatibilityResult(
        goals_alignment=round(goals, 2),
        values_alignment=round(values, 2),
        lifestyle_alignment=round(lifestyle, 2),
        reciprocity=round(reciprocity_score, 2),
        uncertainty=uncertainty,
        explanation=explanation,
    )
