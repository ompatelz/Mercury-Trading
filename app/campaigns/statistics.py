"""Transparent statistical evidence helpers for research-only campaign validation."""

from __future__ import annotations

import math
import random


def bootstrap_interval(
    values: list[float], *, samples: int = 500, seed: int = 17
) -> dict[str, float]:
    if len(values) < 5:
        raise ValueError("at least five observations are required for uncertainty estimates")
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(values) for _ in values) / len(values) for _ in range(samples))
    return {
        "mean": sum(values) / len(values),
        "lower": means[int(samples * 0.025)],
        "upper": means[int(samples * 0.975)],
    }


def compare_baseline(
    candidate: dict[str, float], baseline: dict[str, float]
) -> dict[str, float | bool]:
    return {
        "sharpe_delta": candidate["sharpe_ratio"] - baseline["sharpe_ratio"],
        "return_delta": candidate["total_return"] - baseline["total_return"],
        "drawdown_delta": candidate["max_drawdown"] - baseline["max_drawdown"],
        "outperforms": candidate["sharpe_ratio"] > baseline["sharpe_ratio"]
        and candidate["total_return"] > baseline["total_return"],
    }


def search_context(
    *, hypotheses_tested: int, selected_sharpe: float
) -> dict[str, float | bool | str]:
    warning = hypotheses_tested >= 20
    adjusted = selected_sharpe / math.sqrt(max(1.0, math.log2(hypotheses_tested + 1)))
    return {
        "hypotheses_tested": float(hypotheses_tested),
        "selection_bias_warning": warning,
        "adjusted_sharpe_evidence": adjusted,
        "limitation": "Heuristic search-size adjustment; not a formal deflated Sharpe ratio.",
    }


def ablation(
    full: dict[str, float], reduced: dict[str, float], component: str
) -> dict[str, float | str]:
    return {
        "removed_component": component,
        "sharpe_delta": full["sharpe_ratio"] - reduced["sharpe_ratio"],
        "return_delta": full["total_return"] - reduced["total_return"],
        "drawdown_delta": full["max_drawdown"] - reduced["max_drawdown"],
    }
