"""Transparent, seeded stress testing utilities.

These functions analyse a realised return path.  They produce simulation-based
estimates, not forecasts or guarantees, and intentionally keep every input and
transformation in the returned study payload.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

ScenarioType = Literal[
    "transaction_cost", "slippage", "volatility", "return_shift", "delayed_execution"
]


@dataclass(frozen=True)
class StressScenario:
    scenario_type: ScenarioType
    parameters: dict[str, float | int]
    version: str = "stress-scenario-v1"
    description: str = ""
    affected_components: tuple[str, ...] = ("returns",)


def apply_scenario(
    returns: list[float], scenario: StressScenario, trade_indexes: list[int] | None = None
) -> list[float]:
    """Apply an explicit deterministic transformation to a realised return path."""
    values = np.asarray(returns, dtype=float).copy()
    if scenario.scenario_type in {"transaction_cost", "slippage"}:
        additional_bps = float(scenario.parameters.get("additional_bps", 0.0))
        indexes = trade_indexes if trade_indexes is not None else list(range(len(values)))
        for index in indexes:
            if 0 <= index < len(values):
                values[index] -= additional_bps / 10_000.0
    elif scenario.scenario_type == "volatility":
        multiplier = float(scenario.parameters.get("multiplier", 1.0))
        values *= multiplier
    elif scenario.scenario_type == "return_shift":
        values += float(scenario.parameters.get("per_period_shift", 0.0))
    elif scenario.scenario_type == "delayed_execution":
        delay = int(scenario.parameters.get("bars", 1))
        penalty_bps = float(scenario.parameters.get("penalty_bps", 0.0))
        indexes = trade_indexes if trade_indexes is not None else list(range(len(values)))
        for index in indexes:
            target = index + delay
            if 0 <= target < len(values):
                values[target] -= penalty_bps / 10_000.0
    else:  # pragma: no cover - protects callers that bypass the type checker
        raise ValueError(f"unsupported stress scenario: {scenario.scenario_type}")
    return values.tolist()


def path_metrics(returns: list[float]) -> dict[str, float]:
    values = np.asarray(returns, dtype=float)
    return _path_metrics_array(values)


def _path_metrics_array(values: np.ndarray[Any, Any]) -> dict[str, float]:
    equity = np.cumprod(1.0 + values)
    if values.size == 0:
        return {"total_return": 0.0, "sharpe_ratio": 0.0, "max_drawdown": 0.0, "volatility": 0.0}
    annualization = np.sqrt(252.0)
    deviation = float(np.std(values, ddof=1)) if values.size >= 2 else 0.0
    sharpe = float(np.mean(values) / deviation * annualization) if deviation else 0.0
    running_max = np.maximum.accumulate(equity)
    return {
        "total_return": float(equity[-1] - 1.0),
        "sharpe_ratio": sharpe,
        "max_drawdown": float((equity / running_max - 1.0).min()),
        "volatility": float(deviation * annualization),
    }


def block_bootstrap(
    returns: list[float], *, block_size: int, simulations: int, seed: int
) -> list[dict[str, float]]:
    """Circular moving-block bootstrap that retains local serial dependence."""
    if len(returns) < 2:
        raise ValueError("block bootstrap requires at least two returns")
    if block_size < 1 or block_size > len(returns):
        raise ValueError("block_size must be between one and the number of returns")
    if simulations < 1:
        raise ValueError("simulations must be positive")
    values, rng = np.asarray(returns, dtype=float), np.random.default_rng(seed)
    results: list[dict[str, float]] = []
    blocks_per_sample = int(np.ceil(len(values) / block_size))
    offsets = np.arange(block_size)
    for _ in range(simulations):
        starts = rng.integers(0, len(values), size=blocks_per_sample)
        indexes = (starts[:, None] + offsets) % len(values)
        sampled = values[indexes].reshape(-1)[: len(values)]
        results.append(_path_metrics_array(sampled))
    return results


def summarize_monte_carlo(samples: list[dict[str, float]]) -> dict[str, float]:
    if not samples:
        raise ValueError("at least one simulation result is required")
    values = {key: np.asarray([sample[key] for sample in samples]) for key in samples[0]}
    return {
        "median_final_return": float(np.median(values["total_return"])),
        "median_max_drawdown": float(np.median(values["max_drawdown"])),
        "p95_max_drawdown": float(np.quantile(values["max_drawdown"], 0.05)),
        "probability_negative_terminal_return": float(np.mean(values["total_return"] < 0.0)),
        "probability_sharpe_below_zero": float(np.mean(values["sharpe_ratio"] < 0.0)),
    }


def performance_concentration(
    returns: list[float], timestamps: list[str]
) -> dict[str, float | str]:
    if len(returns) != len(timestamps):
        raise ValueError("returns and timestamps must have the same length")
    positive = np.maximum(np.asarray(returns, dtype=float), 0.0)
    total = float(positive.sum())
    if total == 0.0:
        return {"top_period_profit_share": 0.0, "top_period": "unavailable"}
    index = int(np.argmax(positive))
    return {
        "top_period_profit_share": float(positive[index] / total),
        "top_period": timestamps[index],
    }


def robustness_score(
    *,
    baseline: dict[str, float],
    stressed: list[dict[str, Any]],
    monte_carlo: dict[str, float],
    concentration: dict[str, float | str],
) -> tuple[float, dict[str, float], list[str]]:
    cost_studies = [
        item
        for item in stressed
        if item["scenario"]["scenario_type"] in {"transaction_cost", "slippage"}
    ]
    sharpe_ratio_to_baseline = min(
        (
            max(0.0, item["metrics"]["sharpe_ratio"]) / max(abs(baseline["sharpe_ratio"]), 0.1)
            for item in cost_studies
        ),
        default=1.0,
    )
    components = {
        "cost_sensitivity": min(1.0, sharpe_ratio_to_baseline),
        "monte_carlo_outcomes": max(0.0, 1.0 - monte_carlo["probability_negative_terminal_return"]),
        "drawdown_distribution": max(0.0, 1.0 + monte_carlo["p95_max_drawdown"]),
        "performance_concentration": max(
            0.0, 1.0 - float(concentration["top_period_profit_share"])
        ),
    }
    score = round(100.0 * sum(components.values()) / len(components), 4)
    flags: list[str] = []
    if components["cost_sensitivity"] < 0.65:
        flags.append("COST_SENSITIVITY_HIGH")
    if monte_carlo["p95_max_drawdown"] < -0.35:
        flags.append("MONTE_CARLO_DRAWDOWN_HIGH")
    if monte_carlo["probability_negative_terminal_return"] > 0.35:
        flags.append("TAIL_RISK_HIGH")
    if float(concentration["top_period_profit_share"]) > 0.35:
        flags.extend(["PERFORMANCE_CONCENTRATION_HIGH", "SINGLE_PERIOD_DEPENDENCE"])
    return score, {key: round(value, 6) for key, value in components.items()}, flags


def correlation_stress(return_matrix: list[list[float]], weights: list[float]) -> dict[str, float]:
    """Stress diversification by replacing off-diagonal correlation with one."""
    matrix, allocation = np.asarray(return_matrix, dtype=float), np.asarray(weights, dtype=float)
    if matrix.ndim != 2 or matrix.shape[1] != allocation.size:
        raise ValueError("return matrix columns must match portfolio weights")
    vols = np.std(matrix, axis=0, ddof=1)
    stressed_volatility = float(np.dot(np.abs(allocation), vols))
    baseline_volatility = float(np.std(matrix @ allocation, ddof=1))
    return {
        "baseline_volatility": baseline_volatility,
        "correlation_one_volatility": stressed_volatility,
        "volatility_multiplier": stressed_volatility / max(baseline_volatility, 1e-12),
    }
