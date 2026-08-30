from app.stress_testing.engine import (
    StressScenario,
    apply_scenario,
    block_bootstrap,
    correlation_stress,
    path_metrics,
    performance_concentration,
    robustness_score,
    summarize_monte_carlo,
)


def test_scenarios_are_explicit_and_deterministic() -> None:
    returns = [0.01, -0.01, 0.02, 0.005]
    scenario = StressScenario("transaction_cost", {"additional_bps": 10.0})

    assert apply_scenario(returns, scenario, [1, 3]) == [0.01, -0.011, 0.02, 0.004]
    delayed = apply_scenario(
        returns, StressScenario("delayed_execution", {"bars": 1, "penalty_bps": 5.0}), [0]
    )
    assert delayed == [0.01, -0.0105, 0.02, 0.005]


def test_block_bootstrap_is_seeded_and_aggregated() -> None:
    returns = [0.01, -0.02, 0.015, 0.005, -0.01, 0.02]
    first = block_bootstrap(returns, block_size=2, simulations=8, seed=17)

    assert first == block_bootstrap(returns, block_size=2, simulations=8, seed=17)
    assert len(first) == 8
    summary = summarize_monte_carlo(first)
    assert set(summary) == {
        "median_final_return",
        "median_max_drawdown",
        "p95_max_drawdown",
        "probability_negative_terminal_return",
        "probability_sharpe_below_zero",
    }


def test_vectorized_block_bootstrap_preserves_circular_block_sequence() -> None:
    returns = [0.01, -0.02, 0.015, 0.005, -0.01, 0.02]
    samples = block_bootstrap(returns, block_size=2, simulations=3, seed=17)

    assert samples == block_bootstrap(returns, block_size=2, simulations=3, seed=17)
    expected_metrics = {"total_return", "sharpe_ratio", "max_drawdown", "volatility"}
    assert all(set(sample) == expected_metrics for sample in samples)


def test_robustness_flags_concentration_and_correlation_stress() -> None:
    baseline = path_metrics([0.01, 0.01, 0.01])
    concentration = performance_concentration([0.01, 0.0, 0.0], ["a", "b", "c"])
    score, components, flags = robustness_score(
        baseline=baseline,
        stressed=[
            {
                "scenario": {"scenario_type": "transaction_cost"},
                "metrics": {"sharpe_ratio": 0.0},
            }
        ],
        monte_carlo={
            "probability_negative_terminal_return": 0.5,
            "p95_max_drawdown": -0.4,
        },
        concentration=concentration,
    )

    assert score < 50
    assert components["cost_sensitivity"] == 0.0
    assert {"COST_SENSITIVITY_HIGH", "MONTE_CARLO_DRAWDOWN_HIGH", "TAIL_RISK_HIGH"} <= set(flags)
    assert "PERFORMANCE_CONCENTRATION_HIGH" in flags
    stress = correlation_stress([[0.01, 0.01], [-0.01, -0.01], [0.02, 0.02]], [0.5, 0.5])
    assert stress["volatility_multiplier"] >= 1.0
