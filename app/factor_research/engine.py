"""Pure factor calculations. Each timestamp is evaluated only against its own cross section."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from math import ceil
from typing import Any, Literal

import numpy as np

from app.backtesting.metrics import TRADING_DAYS_PER_YEAR
from app.factor_research.schemas import ForwardReturn, ScorePoint


@dataclass(frozen=True)
class RankedScore:
    timestamp: str
    asset_id: str
    score: float
    rank: int
    percentile: float
    zscore: float
    sector: str | None = None
    size: float | None = None
    volatility: float | None = None


def compute_price_factor(
    prices: dict[str, list[tuple[datetime, float]]],
    *,
    lookback: int,
    transformation: Literal["trailing_return", "inverse_trailing_volatility"],
) -> list[ScorePoint]:
    """Build the initially supported price-only factors from trailing observations.

    The score at index *t* uses prices through *t* only. Fundamental factors are
    intentionally not synthesized until point-in-time fundamental inputs exist.
    """
    if lookback < 1:
        raise ValueError("lookback must be positive")
    result: list[ScorePoint] = []
    for asset_id, history in sorted(prices.items()):
        ordered = sorted(history, key=lambda item: item[0])
        for index in range(lookback, len(ordered)):
            timestamp, price = ordered[index]
            prior = ordered[index - lookback][1]
            if prior <= 0 or price <= 0:
                continue
            if transformation == "trailing_return":
                score = price / prior - 1.0
                volatility = None
            else:
                window = np.array(
                    [item[1] for item in ordered[index - lookback : index + 1]], dtype=float
                )
                returns = window[1:] / window[:-1] - 1.0
                deviation = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
                score, volatility = (-deviation if deviation else 0.0), deviation
            result.append(
                ScorePoint(
                    timestamp=timestamp,
                    asset_id=asset_id,
                    score=float(score),
                    volatility=volatility,
                )
            )
    return result


def rank_scores(
    points: list[ScorePoint], *, direction: Literal["high", "low"] = "high"
) -> list[RankedScore]:
    """Rank per timestamp; missing scores are excluded and ties break by stable asset id."""
    grouped: dict[str, list[ScorePoint]] = defaultdict(list)
    for point in points:
        if point.score is not None and np.isfinite(point.score):
            grouped[point.timestamp.isoformat()].append(point)
    output: list[RankedScore] = []
    for timestamp in sorted(grouped):
        rows = grouped[timestamp]
        ordered = sorted(rows, key=lambda row: (_directional_score(row, direction), row.asset_id))
        values: Any = np.array([_score(row) for row in ordered], dtype=float)
        mean, deviation = float(values.mean()), float(values.std(ddof=0))
        count = len(ordered)
        for index, row in enumerate(ordered, start=1):
            output.append(
                RankedScore(
                    timestamp,
                    row.asset_id,
                    _score(row),
                    index,
                    (count - index + 1) / count,
                    0.0 if deviation == 0 else (_score(row) - mean) / deviation,
                    row.sector,
                    row.size,
                    row.volatility,
                )
            )
    return output


def normalize_scores(
    points: list[ScorePoint],
    method: Literal["raw", "winsorized_zscore", "zscore", "rank"] = "winsorized_zscore",
    *,
    winsor_limit: float = 0.05,
) -> list[ScorePoint]:
    """Cross-sectional preprocessing, never fitted over future dates."""
    if not 0.0 <= winsor_limit < 0.5:
        raise ValueError("winsor_limit must be in [0, 0.5)")
    grouped: dict[str, list[ScorePoint]] = defaultdict(list)
    for point in points:
        if point.score is not None and np.isfinite(point.score):
            grouped[point.timestamp.isoformat()].append(point)
    result: list[ScorePoint] = []
    for timestamp in sorted(grouped):
        rows = grouped[timestamp]
        values: Any = np.array([_score(row) for row in rows], dtype=float)
        if method == "raw":
            result.extend(rows)
            continue
        if method == "winsorized_zscore":
            lower, upper = np.quantile(values, [winsor_limit, 1.0 - winsor_limit])
            values = np.clip(values, lower, upper)
        if method in {"winsorized_zscore", "zscore"}:
            std = float(values.std(ddof=0))
            values = np.zeros(len(values)) if std == 0 else (values - values.mean()) / std
        else:
            ranks = rank_scores(rows)
            values = np.array(
                [
                    next(item.percentile for item in ranks if item.asset_id == row.asset_id)
                    for row in rows
                ]
            )
        result.extend(
            row.model_copy(update={"score": float(values[index])}) for index, row in enumerate(rows)
        )
    return result


def combine_scores(
    factor_scores: dict[str, list[ScorePoint]], weights: dict[str, float] | None = None
) -> list[ScorePoint]:
    """Intersect point-in-time factor observations and combine them transparently."""
    if not factor_scores:
        raise ValueError("at least one factor is required")
    resolved_weights = weights or {name: 1.0 for name in factor_scores}
    unknown = set(resolved_weights) - set(factor_scores)
    if unknown:
        raise ValueError(f"unknown factor weights: {sorted(unknown)}")
    by_factor = {
        name: {(item.timestamp, item.asset_id): item for item in values if item.score is not None}
        for name, values in factor_scores.items()
    }
    keys = set.intersection(*(set(values) for values in by_factor.values()))
    denominator = sum(abs(resolved_weights.get(name, 1.0)) for name in factor_scores)
    if denominator == 0:
        raise ValueError("factor weights cannot all be zero")
    result: list[ScorePoint] = []
    for timestamp, asset_id in sorted(keys):
        source = next(iter(by_factor.values()))[(timestamp, asset_id)]
        value = (
            sum(
                _score(by_factor[name][(timestamp, asset_id)]) * resolved_weights.get(name, 1.0)
                for name in factor_scores
            )
            / denominator
        )
        result.append(source.model_copy(update={"score": value}))
    return result


def construct_weights(
    ranked: list[RankedScore],
    *,
    selection: Literal["top_n", "top_bottom_quantile"],
    top_n: int | None = None,
    quantile: float | None = None,
    method: Literal["equal_weight", "score_weight", "inverse_volatility"] = "equal_weight",
    neutralization: Literal["none", "sector", "size"] = "none",
) -> list[dict[str, float | str]]:
    """Build long-only or symmetric long/short weights per date with explicit neutralization."""
    grouped: dict[str, list[RankedScore]] = defaultdict(list)
    for row in ranked:
        grouped[row.timestamp].append(row)
    result: list[dict[str, float | str]] = []
    for timestamp in sorted(grouped):
        rows = sorted(grouped[timestamp], key=lambda item: item.rank)
        count = len(rows)
        if selection == "top_n":
            selected = rows[: min(top_n or 0, count)]
            signs = [1.0] * len(selected)
        else:
            bucket = max(1, ceil(count * float(quantile or 0)))
            selected, signs = rows[:bucket] + rows[-bucket:], [1.0] * bucket + [-1.0] * bucket
        weights = _raw_weights(selected, signs, method)
        weights = _neutralize(weights, selected, neutralization)
        for row, weight in zip(selected, weights, strict=True):
            result.append(
                {
                    "timestamp": timestamp,
                    "asset_id": row.asset_id,
                    "weight": round(float(weight), 12),
                }
            )
    return result


def evaluate_factor(
    ranked: list[RankedScore], forward_returns: list[ForwardReturn], *, quantiles: int = 5
) -> dict[str, object]:
    """IC, rank IC, quantiles, decay, and turnover from aligned future labels only."""
    if quantiles < 2:
        raise ValueError("quantiles must be at least two")
    lookup = {
        (item.timestamp.isoformat(), item.asset_id, item.horizon): item.value
        for item in forward_returns
    }
    by_time: dict[str, list[RankedScore]] = defaultdict(list)
    for item in ranked:
        by_time[item.timestamp].append(item)
    daily: list[dict[str, float | str]] = []
    quantile_returns: dict[int, list[float]] = defaultdict(list)
    horizon_ics: dict[int, list[float]] = defaultdict(list)
    previous_top: set[str] | None = None
    rank_turnovers: list[float] = []
    for timestamp in sorted(by_time):
        rows = sorted(by_time[timestamp], key=lambda item: item.rank)
        observed = [
            (row, lookup[(timestamp, row.asset_id, 1)])
            for row in rows
            if (timestamp, row.asset_id, 1) in lookup
        ]
        if len(observed) >= 2:
            scores, returns = (
                np.array([row.score for row, _ in observed]),
                np.array([value for _, value in observed]),
            )
            ic = _safe_corr(scores, returns)
            rank_ic = _safe_corr(
                -np.array([row.rank for row, _ in observed]), _ordinal_rank(returns)
            )
            daily.append({"timestamp": timestamp, "ic": ic, "rank_ic": rank_ic})
            for index, (_row, value) in enumerate(observed):
                bucket = min(quantiles, index * quantiles // len(observed) + 1)
                quantile_returns[bucket].append(float(value))
        for horizon in sorted({item.horizon for item in forward_returns}):
            observed_h = [
                (row.score, lookup[(timestamp, row.asset_id, horizon)])
                for row in rows
                if (timestamp, row.asset_id, horizon) in lookup
            ]
            if len(observed_h) >= 2:
                horizon_ics[horizon].append(
                    _safe_corr(
                        np.array([item[0] for item in observed_h]),
                        np.array([item[1] for item in observed_h]),
                    )
                )
        top = {row.asset_id for row in rows[: max(1, ceil(len(rows) * 0.2))]}
        if previous_top is not None:
            rank_turnovers.append(1.0 - len(top & previous_top) / max(1, len(top)))
        previous_top = top
    ic_values = [float(item["ic"]) for item in daily]
    return {
        "ic": _summary(ic_values),
        "rank_ic": _summary([float(item["rank_ic"]) for item in daily]),
        "ic_series": daily,
        "quantiles": {
            f"Q{bucket}": float(np.mean(values)) if values else 0.0
            for bucket, values in sorted(quantile_returns.items())
        },
        "top_bottom_spread": _spread(quantile_returns, quantiles),
        "decay": {
            str(horizon): _summary(values) for horizon, values in sorted(horizon_ics.items())
        },
        "rank_turnover": float(np.mean(rank_turnovers)) if rank_turnovers else 0.0,
    }


def factor_exposures(
    portfolio_weights: list[dict[str, float | str]], ranked_factors: dict[str, list[RankedScore]]
) -> dict[str, float]:
    by_factor = {
        name: {(row.timestamp, row.asset_id): row.zscore for row in rows}
        for name, rows in ranked_factors.items()
    }
    return {
        name: round(
            float(
                sum(
                    float(row["weight"])
                    * values.get((str(row["timestamp"]), str(row["asset_id"])), 0.0)
                    for row in portfolio_weights
                )
            ),
            8,
        )
        for name, values in by_factor.items()
    }


def robustness_flags(
    ranked: list[RankedScore], weights: list[dict[str, float | str]], *, minimum_breadth: int = 5
) -> list[str]:
    flags: list[str] = []
    if len({row.asset_id for row in ranked}) < minimum_breadth:
        flags.append("LOW_CROSS_SECTIONAL_BREADTH")
    sector_weight: dict[str, float] = defaultdict(float)
    for weight in weights:
        matched = next(
            (
                item
                for item in ranked
                if item.timestamp == weight["timestamp"] and item.asset_id == weight["asset_id"]
            ),
            None,
        )
        if matched and matched.sector:
            sector_weight[matched.sector] += abs(float(weight["weight"]))
    if sector_weight and max(sector_weight.values()) / sum(sector_weight.values()) > 0.6:
        flags.append("SECTOR_DEPENDENCE_HIGH")
    return flags


def _raw_weights(rows: list[RankedScore], signs: list[float], method: str) -> np.ndarray[Any, Any]:
    if not rows:
        return np.array([], dtype=float)
    if method == "equal_weight":
        raw = np.ones(len(rows))
    elif method == "score_weight":
        raw = np.maximum(np.abs(np.array([row.zscore for row in rows])), 1e-8)
    else:
        raw = 1.0 / np.maximum(
            np.array(
                [row.volatility if row.volatility and row.volatility > 0 else 1.0 for row in rows]
            ),
            1e-8,
        )
    raw = raw / raw.sum()
    return np.asarray(raw * np.array(signs), dtype=float)


def _neutralize(weights: np.ndarray, rows: list[RankedScore], method: str) -> np.ndarray:
    if method == "none" or not len(weights):
        return weights
    values = np.array(
        [row.size if method == "size" and row.size is not None else 0.0 for row in rows]
    )
    if method == "sector":
        groups = [row.sector or "UNKNOWN" for row in rows]
        adjusted = weights.copy()
        for group in sorted(set(groups)):
            positions = [index for index, value in enumerate(groups) if value == group]
            adjusted[positions] -= adjusted[positions].mean()
        return adjusted
    centered = values - values.mean()
    denominator = float(centered @ centered)
    return (
        weights
        if denominator == 0
        else weights - centered * float(centered @ weights) / denominator
    )


def _safe_corr(left: np.ndarray, right: np.ndarray) -> float:
    return (
        0.0
        if len(left) < 2 or np.std(left) == 0 or np.std(right) == 0
        else round(float(np.corrcoef(left, right)[0, 1]), 8)
    )


def _ordinal_rank(values: np.ndarray) -> np.ndarray:
    ranks = np.empty(len(values), dtype=float)
    for rank, (index, _value) in enumerate(sorted(enumerate(values), key=lambda item: item[1])):
        ranks[index] = rank
    return ranks


def _score(row: ScorePoint) -> float:
    if row.score is None:
        raise ValueError("score is required after missing-score filtering")
    return float(row.score)


def _directional_score(row: ScorePoint, direction: Literal["high", "low"]) -> float:
    score = _score(row)
    return -score if direction == "high" else score


def _summary(values: list[float]) -> dict[str, float]:
    mean = float(np.mean(values)) if values else 0.0
    std = float(np.std(values, ddof=1)) if len(values) > 1 else 0.0
    return {
        "mean": round(mean, 8),
        "information_ratio": round(mean / std * np.sqrt(TRADING_DAYS_PER_YEAR), 8) if std else 0.0,
        "observations": float(len(values)),
    }


def _spread(values: dict[int, list[float]], quantiles: int) -> float:
    return round(
        (float(np.mean(values.get(1, [0.0]))) - float(np.mean(values.get(quantiles, [0.0])))), 8
    )
