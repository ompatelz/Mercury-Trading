"""Auditable, no-lookahead portfolio construction for research use."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

import numpy as np

from app.backtesting.metrics import (
    annualized_return,
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
    total_return,
    volatility,
)

AllocationMethod = Literal["equal_weight", "inverse_volatility", "risk_parity"]
DynamicMethod = Literal["static", "volatility_scaling", "risk_based", "performance_aware"]


@dataclass(frozen=True)
class StrategySeries:
    strategy_id: str
    version: str
    family: str
    symbol: str
    returns: list[dict[str, float | str]]
    regime_performance: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PortfolioDefinition:
    strategy_ids: list[str]
    strategy_versions: dict[str, str]
    allocation_method: AllocationMethod
    dynamic_method: DynamicMethod = "static"
    rebalance_frequency: Literal["weekly", "monthly"] = "monthly"
    lookback_periods: int = 20
    constraints: dict[str, float] = field(default_factory=dict)
    universe: list[str] = field(default_factory=list)
    validation_period: dict[str, str] = field(default_factory=dict)
    transaction_cost_bps: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "strategy_ids": self.strategy_ids,
            "strategy_versions": self.strategy_versions,
            "allocation_method": self.allocation_method,
            "dynamic_method": self.dynamic_method,
            "rebalance_frequency": self.rebalance_frequency,
            "lookback_periods": self.lookback_periods,
            "constraints": self.constraints,
            "universe": self.universe,
            "validation_period": self.validation_period,
            "transaction_cost_bps": self.transaction_cost_bps,
            "data_policy": "weights at t use only returns strictly before t",
        }


@dataclass(frozen=True)
class PortfolioResult:
    weights: dict[str, float]
    metrics: dict[str, Any]
    compatibility: dict[str, Any]
    return_series: list[dict[str, Any]]
    rebalance_history: list[dict[str, Any]]
    rejection_reasons: list[str]
    incremental_benefit: dict[str, dict[str, float]]


def construct_portfolio(
    definition: PortfolioDefinition, strategies: list[StrategySeries]
) -> PortfolioResult:
    """Combine aligned strategy returns, never final strategy-level summaries."""
    _validate_definition(definition, strategies)
    dates, matrix = _aligned_returns(strategies)
    base_weights = allocate(
        matrix, [item.strategy_id for item in strategies], definition.allocation_method
    )
    reasons = validate_constraints(base_weights, strategies, definition.constraints)
    if reasons:
        return PortfolioResult(
            weights=base_weights,
            metrics={"status": "rejected", "rejection_reasons": reasons},
            compatibility=compatibility(strategies, matrix),
            return_series=[],
            rebalance_history=[],
            rejection_reasons=reasons,
            incremental_benefit={},
        )
    series, rebalances = _simulate(dates, matrix, strategies, definition, base_weights)
    portfolio_returns = np.array([float(point["return"]) for point in series], dtype=float)
    equity = _equity(portfolio_returns)
    metrics = _metrics(portfolio_returns, equity, matrix, base_weights, series)
    metrics["status"] = "valid"
    return PortfolioResult(
        weights=base_weights,
        metrics=metrics,
        compatibility=compatibility(strategies, matrix),
        return_series=series,
        rebalance_history=rebalances,
        rejection_reasons=[],
        incremental_benefit=_incremental_benefit(matrix, strategies, definition),
    )


def allocate(matrix: np.ndarray, ids: list[str], method: AllocationMethod) -> dict[str, float]:
    if len(ids) == 0:
        raise ValueError("portfolio requires at least one strategy")
    if method == "equal_weight":
        raw = np.ones(len(ids), dtype=float)
    else:
        vols = np.std(matrix, axis=0, ddof=1) if matrix.shape[0] > 1 else np.ones(len(ids))
        vols = np.maximum(vols, 1e-8)
        if method == "inverse_volatility":
            raw = 1.0 / vols
        elif method == "risk_parity":
            raw = _risk_parity_weights(np.cov(matrix, rowvar=False, ddof=1))
        else:
            raise ValueError("unsupported allocation method")
    normalized = raw / raw.sum()
    return {
        strategy_id: round(float(normalized[index]), 12) for index, strategy_id in enumerate(ids)
    }


def validate_constraints(
    weights: dict[str, float], strategies: list[StrategySeries], constraints: dict[str, float]
) -> list[str]:
    reasons: list[str] = []
    minimum = float(constraints.get("min_strategy_weight", 0.0))
    maximum = float(constraints.get("max_strategy_weight", 1.0))
    leverage = sum(abs(weight) for weight in weights.values())
    if any(weight < minimum - 1e-12 for weight in weights.values()):
        reasons.append("minimum strategy weight violated")
    if any(weight > maximum + 1e-12 for weight in weights.values()):
        reasons.append("maximum strategy weight violated")
    if leverage > float(constraints.get("max_portfolio_leverage", 1.0)) + 1e-12:
        reasons.append("maximum portfolio leverage violated")
    for attribute, label in [
        ("family", "maximum family exposure"),
        ("symbol", "maximum asset exposure"),
    ]:
        cap = constraints.get(f"max_{attribute}_exposure")
        if cap is None:
            continue
        grouped: dict[str, float] = {}
        for strategy in strategies:
            key = getattr(strategy, attribute)
            grouped[key] = grouped.get(key, 0.0) + abs(weights[strategy.strategy_id])
        if any(exposure > float(cap) + 1e-12 for exposure in grouped.values()):
            reasons.append(f"{label} violated")
    return reasons


def compatibility(strategies: list[StrategySeries], matrix: np.ndarray) -> dict[str, Any]:
    ids = [item.strategy_id for item in strategies]
    correlation = np.corrcoef(matrix, rowvar=False) if len(ids) > 1 else np.array([[1.0]])
    if correlation.ndim == 0:
        correlation = np.array([[1.0]])
    pairs: list[dict[str, Any]] = []
    for left in range(len(ids)):
        for right in range(left + 1, len(ids)):
            a, b = matrix[:, left], matrix[:, right]
            drawdown_a, drawdown_b = _drawdowns(a), _drawdowns(b)
            pairs.append(
                {
                    "left": ids[left],
                    "right": ids[right],
                    "return_correlation": round(float(correlation[left, right]), 8),
                    "signal_correlation": round(float(_safe_corr(np.sign(a), np.sign(b))), 8),
                    "trade_overlap": round(float(np.mean((a != 0.0) & (b != 0.0))), 8),
                    "drawdown_overlap": round(
                        float(np.mean((drawdown_a < 0.0) & (drawdown_b < 0.0))), 8
                    ),
                    "same_family": strategies[left].family == strategies[right].family,
                    "regime_dependence": _regime_dependence(strategies[left], strategies[right]),
                }
            )
    return {"columns": ids, "matrix": np.round(correlation, 8).tolist(), "pairs": pairs}


def _simulate(
    dates: list[str],
    matrix: np.ndarray,
    strategies: list[StrategySeries],
    definition: PortfolioDefinition,
    initial_weights: dict[str, float],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ids = [item.strategy_id for item in strategies]
    weights = np.array([initial_weights[item] for item in ids], dtype=float)
    previous = weights.copy()
    history: list[dict[str, Any]] = []
    points: list[dict[str, Any]] = []
    cost_rate = definition.transaction_cost_bps / 10_000.0
    for index, timestamp in enumerate(dates):
        if (
            _should_rebalance(
                timestamp, dates[index - 1] if index else None, definition.rebalance_frequency
            )
            and index >= definition.lookback_periods
        ):
            # The slice ends at index: no contemporaneous/future return is used.
            weights = _dynamic_weights(matrix[:index], ids, definition, weights)
            turnover = float(np.abs(weights - previous).sum())
            maximum_turnover = definition.constraints.get("max_turnover")
            if maximum_turnover is not None and turnover > float(maximum_turnover):
                weights = previous.copy()
                history.append(
                    {
                        "timestamp": timestamp,
                        "reason": "rejected: maximum turnover",
                        "turnover": turnover,
                    }
                )
            else:
                history.append(
                    {
                        "timestamp": timestamp,
                        "reason": definition.dynamic_method,
                        "old_weights": _weights(ids, previous),
                        "new_weights": _weights(ids, weights),
                        "turnover": turnover,
                        "transaction_cost": turnover * cost_rate,
                    }
                )
                previous = weights.copy()
        turnover_cost = (
            float(history[-1].get("transaction_cost", 0.0))
            if history and history[-1].get("timestamp") == timestamp
            else 0.0
        )
        contribution = weights * matrix[index]
        turnover = (
            float(history[-1].get("turnover", 0.0))
            if history and history[-1].get("timestamp") == timestamp
            else 0.0
        )
        points.append(
            {
                "timestamp": timestamp,
                "return": float(contribution.sum() - turnover_cost),
                "transaction_cost": turnover_cost,
                "turnover": turnover,
                "contributions": _weights(ids, contribution),
            }
        )
    return points, history


def _dynamic_weights(
    history: np.ndarray, ids: list[str], definition: PortfolioDefinition, prior: np.ndarray
) -> np.ndarray:
    if definition.dynamic_method == "static":
        return prior
    window = history[-definition.lookback_periods :]
    if definition.dynamic_method in {"volatility_scaling", "risk_based"}:
        values = np.array(list(allocate(window, ids, "inverse_volatility").values()))
    else:
        performance = np.maximum(np.mean(window, axis=0), 0.0) + 1e-8
        values = performance / performance.sum()
    return np.asarray(values / values.sum(), dtype=float)


def _aligned_returns(strategies: list[StrategySeries]) -> tuple[list[str], np.ndarray]:
    by_strategy = [
        {str(point["timestamp"]): float(point["return"]) for point in item.returns}
        for item in strategies
    ]
    dates = sorted(set.intersection(*(set(points) for points in by_strategy)))
    if len(dates) < 2:
        raise ValueError("portfolio requires at least two aligned return observations")
    return dates, np.array(
        [[points[date] for points in by_strategy] for date in dates], dtype=float
    )


def _metrics(
    returns: np.ndarray,
    equity: np.ndarray,
    matrix: np.ndarray,
    weights: dict[str, float],
    points: list[dict[str, Any]],
) -> dict[str, Any]:
    import polars as pl

    return_series, equity_series = pl.Series(returns), pl.Series(equity)
    weighted_vol = float(np.std(returns, ddof=1))
    standalone_vol = np.std(matrix, axis=0, ddof=1)
    contribution = {key: 0.0 for key in weights}
    for point in points:
        for key, value in point["contributions"].items():
            contribution[key] += value
    worst = int(np.argmin(returns))
    return {
        "total_return": total_return(equity_series),
        "annualized_return": annualized_return(equity_series),
        "volatility": volatility(return_series),
        "sharpe_ratio": sharpe_ratio(return_series),
        "sortino_ratio": sortino_ratio(return_series),
        "max_drawdown": max_drawdown(equity_series),
        "turnover": round(sum(float(point["turnover"]) for point in points), 8),
        "transaction_cost": round(sum(float(point["transaction_cost"]) for point in points), 10),
        "diversification_ratio": round(
            float(
                np.dot(np.array(list(weights.values())), standalone_vol) / max(weighted_vol, 1e-12)
            ),
            8,
        ),
        "worst_period": points[worst]["timestamp"],
        "strategy_contribution_to_return": contribution,
        "strategy_contribution_to_risk": _risk_contributions(
            matrix, np.array(list(weights.values())), list(weights)
        ),
    }


def _incremental_benefit(
    matrix: np.ndarray, strategies: list[StrategySeries], definition: PortfolioDefinition
) -> dict[str, dict[str, float]]:
    all_ids = [item.strategy_id for item in strategies]
    full = _portfolio_stats(matrix, definition.allocation_method)
    result: dict[str, dict[str, float]] = {}
    for index, strategy in enumerate(strategies):
        remaining = np.delete(matrix, index, axis=1)
        baseline = (
            _portfolio_stats(remaining, definition.allocation_method)
            if remaining.shape[1]
            else {"sharpe_ratio": 0.0, "max_drawdown": 0.0}
        )
        result[strategy.strategy_id] = {
            "sharpe_delta": round(full["sharpe_ratio"] - baseline["sharpe_ratio"], 8),
            "max_drawdown_delta": round(full["max_drawdown"] - baseline["max_drawdown"], 8),
            "portfolio_members": float(len(all_ids)),
        }
    return result


def _portfolio_stats(matrix: np.ndarray, method: AllocationMethod) -> dict[str, float]:
    ids = [str(index) for index in range(matrix.shape[1])]
    weights = np.array(list(allocate(matrix, ids, method).values()))
    returns = matrix @ weights
    equity = _equity(returns)
    import polars as pl

    return {
        "sharpe_ratio": sharpe_ratio(pl.Series(returns)),
        "max_drawdown": max_drawdown(pl.Series(equity)),
    }


def _risk_parity_weights(covariance: np.ndarray) -> np.ndarray:
    if covariance.ndim == 0:
        return np.ones(1)
    weights = np.ones(covariance.shape[0]) / covariance.shape[0]
    for _ in range(100):
        marginal = covariance @ weights
        contributions = weights * marginal
        target = contributions.sum() / len(weights)
        next_weights = weights * target / np.maximum(contributions, 1e-12)
        next_weights /= next_weights.sum()
        if np.max(np.abs(next_weights - weights)) < 1e-10:
            break
        weights = next_weights
    return np.asarray(weights, dtype=float)


def _equity(returns: np.ndarray) -> np.ndarray:
    return np.cumprod(1.0 + returns)


def _drawdowns(returns: np.ndarray) -> np.ndarray:
    equity = _equity(returns)
    return equity / np.maximum.accumulate(equity) - 1.0


def _safe_corr(left: np.ndarray, right: np.ndarray) -> float:
    if len(left) < 2 or np.std(left) == 0 or np.std(right) == 0:
        return 0.0
    return float(np.corrcoef(left, right)[0, 1])


def _regime_dependence(left: StrategySeries, right: StrategySeries) -> str:
    left_bad = {
        key
        for key, value in left.regime_performance.items()
        if isinstance(value, dict) and float(value.get("sharpe_ratio", 0.0)) < 0.0
    }
    right_bad = {
        key
        for key, value in right.regime_performance.items()
        if isinstance(value, dict) and float(value.get("sharpe_ratio", 0.0)) < 0.0
    }
    return "shared" if left_bad & right_bad else "complementary"


def _should_rebalance(current: str, previous: str | None, frequency: str) -> bool:
    if previous is None:
        return False
    if frequency == "weekly":
        current_day = datetime.fromisoformat(current.replace("Z", "+00:00")).date()
        previous_day = datetime.fromisoformat(previous.replace("Z", "+00:00")).date()
        return current_day.isocalendar().week != previous_day.isocalendar().week
    return current[:7] != previous[:7]


def _weights(ids: list[str], values: np.ndarray) -> dict[str, float]:
    return {item: round(float(values[index]), 12) for index, item in enumerate(ids)}


def _risk_contributions(
    matrix: np.ndarray, weights: np.ndarray, ids: list[str]
) -> dict[str, float]:
    covariance = np.cov(matrix, rowvar=False, ddof=1)
    if covariance.ndim == 0:
        return {ids[0]: 1.0}
    marginal = covariance @ weights
    total = max(float(weights @ marginal), 1e-12)
    return {
        ids[index]: round(float(weights[index] * marginal[index] / total), 8)
        for index in range(len(weights))
    }


def _validate_definition(definition: PortfolioDefinition, strategies: list[StrategySeries]) -> None:
    if definition.strategy_ids != [item.strategy_id for item in strategies]:
        raise ValueError("portfolio definition and strategy series differ")
    if definition.lookback_periods < 2:
        raise ValueError("lookback_periods must be at least two")
    if definition.transaction_cost_bps < 0:
        raise ValueError("transaction_cost_bps must be non-negative")
