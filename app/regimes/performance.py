from collections import defaultdict
from typing import Any

import polars as pl

from app.backtesting.metrics import max_drawdown, sharpe_ratio, sortino_ratio, total_return
from app.regimes.engine import RegimeObservation


def performance_by_regime(
    equity_curve: pl.DataFrame,
    observations: list[RegimeObservation],
) -> dict[str, dict[str, float | int]]:
    labels = {observation.timestamp: observation.composite_regime for observation in observations}
    rows_by_regime: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in equity_curve.iter_rows(named=True):
        regime = labels.get(row["timestamp"])
        if regime is not None:
            rows_by_regime[regime].append(row)

    results: dict[str, dict[str, float | int]] = {}
    for regime, rows in rows_by_regime.items():
        frame = pl.DataFrame(rows)
        returns = frame.get_column("strategy_return")
        equity = frame.get_column("equity")
        trade_count = int(sum(1 for row in rows if float(row.get("trade_size", 0.0)) > 0.0))
        turnover = float(sum(float(row.get("trade_size", 0.0)) for row in rows))
        results[regime] = {
            "bars": len(rows),
            "total_return": round(total_return(equity), 8),
            "sharpe_ratio": round(sharpe_ratio(returns), 8),
            "sortino_ratio": round(sortino_ratio(returns), 8),
            "max_drawdown": round(max_drawdown(equity), 8),
            "win_rate": _positive_return_rate(returns),
            "turnover": round(turnover, 8),
            "trade_count": trade_count,
        }
    return results


def regime_robustness_score(
    regime_performance: dict[str, dict[str, float | int]],
    *,
    expected_regimes: int = 4,
) -> tuple[float, list[str], dict[str, float]]:
    if not regime_performance:
        return (
            0.0,
            ["UNTESTED_REGIME"],
            {
                "coverage": 0.0,
                "worst_regime": 0.0,
                "dispersion": 0.0,
                "drawdown": 0.0,
                "trade_support": 0.0,
            },
        )
    sharpes = [float(metrics.get("sharpe_ratio", 0.0)) for metrics in regime_performance.values()]
    drawdowns = [
        abs(float(metrics.get("max_drawdown", 0.0))) for metrics in regime_performance.values()
    ]
    trades = [float(metrics.get("trade_count", 0.0)) for metrics in regime_performance.values()]
    coverage = min(1.0, len(regime_performance) / expected_regimes)
    worst = min(sharpes)
    dispersion = max(sharpes) - min(sharpes) if len(sharpes) > 1 else 0.0
    worst_component = _clamp((worst + 1.0) / 3.0)
    dispersion_component = _clamp(1.0 - dispersion / 4.0)
    drawdown_component = _clamp(1.0 - max(drawdowns, default=0.0))
    trade_component = _clamp(min(trades, default=0.0) / 3.0)
    components = {
        "coverage": round(coverage, 6),
        "worst_regime": round(worst_component, 6),
        "dispersion": round(dispersion_component, 6),
        "drawdown": round(drawdown_component, 6),
        "trade_support": round(trade_component, 6),
    }
    score = round(
        100.0
        * (
            coverage * 0.2
            + worst_component * 0.25
            + dispersion_component * 0.2
            + drawdown_component * 0.2
            + trade_component * 0.15
        ),
        4,
    )
    flags: list[str] = []
    if coverage < 1.0:
        flags.append("UNTESTED_REGIME")
    if worst < 0.0:
        flags.append("REGIME_DEPENDENCE_HIGH")
    if dispersion > 2.0:
        flags.append("REGIME_DEPENDENCE_HIGH")
    if any(
        "high" in regime and float(metrics.get("sharpe_ratio", 0.0)) < 0.0
        for regime, metrics in regime_performance.items()
    ):
        flags.append("HIGH_VOL_FAILURE")
    if any(
        "sideways" in regime and float(metrics.get("sharpe_ratio", 0.0)) < 0.0
        for regime, metrics in regime_performance.items()
    ):
        flags.append("SIDEWAYS_FAILURE")
    return score, list(dict.fromkeys(flags)), components


def _positive_return_rate(returns: pl.Series) -> float:
    values = [float(value) for value in returns.fill_null(0.0).to_list()]
    if not values:
        return 0.0
    return round(sum(1 for value in values if value > 0.0) / len(values), 8)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
