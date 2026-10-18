from app.compatibility.engine import (
    CounterpartProfile,
    assess_compatibility,
    reciprocity_from_counts,
)


def test_reciprocity_from_counts():
    assert reciprocity_from_counts(0, 0) == 0.5
    assert reciprocity_from_counts(5, 5) == 1.0
    assert reciprocity_from_counts(10, 0) == 0.0
    assert reciprocity_from_counts(3, 1) == 0.5


def test_partial_alignment_and_uncertainty():
    result = assess_compatibility(
        user_goals=["семья", "путешествия"],
        user_values=[],
        user_preferences={},
        counterpart=CounterpartProfile(goals=["семья"]),
    )
    assert result.goals_alignment == 0.5
    assert result.values_alignment == 0.0
    assert result.reciprocity == 0.5
    assert result.uncertainty == 0.67


def test_full_counterpart_has_zero_uncertainty():
    result = assess_compatibility(
        user_goals=["семья"],
        user_values=["честность"],
        user_preferences={"smoking": "no"},
        counterpart=CounterpartProfile(
            goals=["семья"], values=["честность"], lifestyle={"smoking": "no"}
        ),
    )
    assert result.goals_alignment == 1.0
    assert result.values_alignment == 1.0
    assert result.lifestyle_alignment == 1.0
    assert result.uncertainty == 0.0
