from dataclasses import replace

from app.campaigns.portfolio import _correlation_stress
from app.portfolio.engine import PortfolioDefinition, StrategySeries, construct_portfolio


def test_allocation_methods_and_combined_accounting_are_deterministic() -> None:
    strategies = _strategies()
    for method in ["equal_weight", "inverse_volatility", "risk_parity"]:
        result = construct_portfolio(_definition(method), strategies)
        assert result.rejection_reasons == []
        assert round(sum(result.weights.values()), 10) == 1.0
        assert len(result.return_series) == 30
        assert "strategy_contribution_to_return" in result.metrics
        assert result.metrics["transaction_cost"] == 0.0
    inverse = construct_portfolio(_definition("inverse_volatility"), strategies)
    assert inverse.weights["stable"] > inverse.weights["volatile"]


def test_constraints_reject_incompatible_portfolio_with_explicit_reasons() -> None:
    result = construct_portfolio(
        _definition("equal_weight", {"max_family_exposure": 0.6}), _strategies()
    )
    assert result.metrics["status"] == "rejected"
    assert result.rejection_reasons == ["maximum family exposure violated"]


def test_dynamic_weights_use_only_prior_returns_and_record_rebalances() -> None:
    strategies = _strategies()
    definition = replace(
        _definition("equal_weight"),
        dynamic_method="performance_aware",
        rebalance_frequency="weekly",
        lookback_periods=5,
    )
    result = construct_portfolio(definition, strategies)
    assert result.rebalance_history
    first = result.rebalance_history[0]
    assert first["timestamp"] == strategies[0].returns[7]["timestamp"]
    assert first["reason"] == "performance_aware"
    assert result.metrics["turnover"] > 0


def test_compatibility_and_incremental_benefit_are_explainable() -> None:
    result = construct_portfolio(_definition("equal_weight"), _strategies())
    pair = result.compatibility["pairs"][0]
    assert pair["same_family"] is True
    assert "trade_overlap" in pair
    assert set(result.incremental_benefit) == {"stable", "volatile"}
    correlation = _correlation_stress(_strategies(), result.weights)
    assert correlation["volatility_multiplier"] >= 1.0


def _definition(method: str, constraints: dict[str, float] | None = None) -> PortfolioDefinition:
    return PortfolioDefinition(
        strategy_ids=["stable", "volatile"],
        strategy_versions={"stable": "v1", "volatile": "v1"},
        allocation_method=method,  # type: ignore[arg-type]
        lookback_periods=5,
        constraints=constraints or {},
        universe=["MSFT"],
        validation_period={"start": "2024-01-01", "end": "2024-01-30"},
    )


def _strategies() -> list[StrategySeries]:
    dates = [f"2024-01-{index + 1:02d}T00:00:00+00:00" for index in range(30)]
    return [
        StrategySeries(
            strategy_id="stable",
            version="v1",
            family="moving_average",
            symbol="MSFT",
            returns=[
                {"timestamp": date, "return": 0.002 + (index % 3) * 0.0005}
                for index, date in enumerate(dates)
            ],
        ),
        StrategySeries(
            strategy_id="volatile",
            version="v1",
            family="moving_average",
            symbol="AAPL",
            returns=[
                {"timestamp": date, "return": 0.02 if index % 2 else -0.015}
                for index, date in enumerate(dates)
            ],
        ),
    ]
