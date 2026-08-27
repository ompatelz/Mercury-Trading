from datetime import UTC, datetime, timedelta

import pytest

from app.factor_research.compiler import compile_factor_strategy
from app.factor_research.engine import (
    combine_scores,
    compute_price_factor,
    construct_weights,
    evaluate_factor,
    normalize_scores,
    rank_scores,
)
from app.factor_research.schemas import (
    FactorDefinition,
    FactorStrategySpec,
    ForwardReturn,
    ScorePoint,
)
from app.factor_research.service import FactorResearchService


def at(day: int) -> datetime:
    return datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=day - 1)


def factor() -> FactorDefinition:
    return FactorDefinition(
        factor_id="momentum",
        name="Momentum",
        version="v1",
        input_features=("adjusted_close",),
        lookback=2,
        transformation="trailing_return",
    )


def strategy(**changes: object) -> FactorStrategySpec:
    return FactorStrategySpec(
        universe_id="etfs-v1",
        factors=(factor(),),
        selection="top_bottom_quantile",
        quantile=0.5,
        weighting="equal_weight",
        **changes,
    )


def scores() -> list[ScorePoint]:
    return [
        ScorePoint(timestamp=at(1), asset_id="B", score=1.0, sector="tech"),
        ScorePoint(timestamp=at(1), asset_id="A", score=1.0, sector="tech"),
        ScorePoint(timestamp=at(1), asset_id="C", score=None, sector="energy"),
        ScorePoint(timestamp=at(2), asset_id="A", score=3.0, sector="tech"),
        ScorePoint(timestamp=at(2), asset_id="B", score=2.0, sector="energy"),
    ]


def test_ranking_is_deterministic_and_missing_scores_are_excluded() -> None:
    ranked = rank_scores(scores())
    assert [
        (item.asset_id, item.rank) for item in ranked if item.timestamp == at(1).isoformat()
    ] == [("A", 1), ("B", 2)]
    assert all(item.asset_id != "C" for item in ranked)


def test_normalization_and_composite_are_cross_sectional() -> None:
    normalized = normalize_scores(scores(), "winsorized_zscore")
    first = [item.score for item in normalized if item.timestamp == at(1)]
    assert sum(first) == pytest.approx(0.0)
    composite = combine_scores({"momentum": normalized})
    assert len(composite) == len(normalized)


def test_price_factor_is_trailing_only() -> None:
    result = compute_price_factor(
        {"A": [(at(1), 100), (at(2), 110), (at(3), 121)]},
        lookback=2,
        transformation="trailing_return",
    )
    assert result[0].score == pytest.approx(0.21)


def test_long_short_weights_and_sector_neutralization_are_explicit() -> None:
    ranked = rank_scores(
        [
            ScorePoint(
                timestamp=at(1),
                asset_id=item,
                score=score,
                sector="tech" if item < "C" else "energy",
            )
            for item, score in [("A", 4.0), ("B", 3.0), ("C", 2.0), ("D", 1.0)]
        ]
    )
    weights = construct_weights(
        ranked, selection="top_bottom_quantile", quantile=0.5, neutralization="sector"
    )
    assert sum(float(item["weight"]) for item in weights) == pytest.approx(0.0)


def test_ic_quantiles_decay_and_turnover_use_only_aligned_forward_labels() -> None:
    ranked = rank_scores(
        [
            ScorePoint(timestamp=at(day), asset_id=asset, score=score)
            for day, score_map in [
                (1, {"A": 3.0, "B": 2.0, "C": 1.0}),
                (2, {"A": 1.0, "B": 2.0, "C": 3.0}),
            ]
            for asset, score in score_map.items()
        ]
    )
    labels = [
        ForwardReturn(timestamp=at(day), asset_id=asset, horizon=horizon, value=value)
        for day, values in [
            (1, {"A": 0.03, "B": 0.02, "C": 0.01}),
            (2, {"A": 0.01, "B": 0.02, "C": 0.03}),
        ]
        for asset, value in values.items()
        for horizon in (1, 5)
    ]
    result = evaluate_factor(ranked, labels, quantiles=3)
    assert result["ic"]["mean"] == pytest.approx(1.0)
    assert result["decay"]["5"]["mean"] == pytest.approx(1.0)
    assert result["top_bottom_spread"] > 0
    assert result["rank_turnover"] == pytest.approx(1.0)


def test_service_compiles_structured_dsl_and_returns_research_evidence() -> None:
    spec = strategy()
    plan = compile_factor_strategy(spec)
    assert "rank point-in-time" in plan.steps
    result = FactorResearchService().evaluate(
        spec,
        {"momentum": scores()},
        [
            ForwardReturn(timestamp=at(1), asset_id="A", horizon=1, value=0.02),
            ForwardReturn(timestamp=at(1), asset_id="B", horizon=1, value=0.01),
            ForwardReturn(timestamp=at(2), asset_id="A", horizon=1, value=0.02),
            ForwardReturn(timestamp=at(2), asset_id="B", horizon=1, value=0.01),
        ],
    )
    assert result["weights"]
    assert "LOW_CROSS_SECTIONAL_BREADTH" in result["robustness_flags"]
