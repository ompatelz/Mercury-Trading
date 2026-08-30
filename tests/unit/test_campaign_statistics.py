import pytest

from app.campaigns.statistics import ablation, bootstrap_interval, compare_baseline, search_context


def test_statistical_evidence_is_seeded_and_reports_search_context() -> None:
    values = [0.01, -0.02, 0.03, 0.0, 0.01, -0.01]
    assert bootstrap_interval(values, seed=9) == bootstrap_interval(values, seed=9)
    with pytest.raises(ValueError, match="five"):
        bootstrap_interval(values[:4])
    candidate = {"sharpe_ratio": 1.5, "total_return": 0.12, "max_drawdown": -0.1}
    baseline = {"sharpe_ratio": 0.8, "total_return": 0.06, "max_drawdown": -0.08}
    assert compare_baseline(candidate, baseline)["outperforms"] is True
    assert (
        search_context(hypotheses_tested=20, selected_sharpe=2.0)["selection_bias_warning"] is True
    )
    assert (
        ablation(candidate, baseline, "volatility_filter")["removed_component"]
        == "volatility_filter"
    )
