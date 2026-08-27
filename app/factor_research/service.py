from __future__ import annotations

from typing import Literal

from app.factor_research.engine import (
    combine_scores,
    construct_weights,
    evaluate_factor,
    factor_exposures,
    normalize_scores,
    rank_scores,
    robustness_flags,
)
from app.factor_research.schemas import FactorStrategySpec, ForwardReturn, ScorePoint


class FactorResearchService:
    """Coordinates structured factor research without future-data side effects."""

    def evaluate(
        self,
        spec: FactorStrategySpec,
        scores: dict[str, list[ScorePoint]],
        forward_returns: list[ForwardReturn],
    ) -> dict[str, object]:
        missing = {item.factor_id for item in spec.factors} - set(scores)
        if missing:
            raise ValueError(f"missing factor scores: {sorted(missing)}")
        prepared = {}
        for factor in spec.factors:
            methods: dict[str, Literal["raw", "winsorized_zscore", "zscore", "rank"]] = {
                "raw": "raw",
                "percentile": "rank",
                "zscore": "zscore",
            }
            method = methods[factor.ranking_method]
            normalized = normalize_scores(scores[factor.factor_id], method)
            if factor.direction == "low":
                normalized = [
                    item.model_copy(update={"score": -item.score})
                    for item in normalized
                    if item.score is not None
                ]
            prepared[factor.factor_id] = normalized
        composite = combine_scores(prepared, spec.factor_weights or None)
        ranked = rank_scores(composite)
        weights = construct_weights(
            ranked,
            selection=spec.selection,
            top_n=spec.top_n,
            quantile=spec.quantile,
            method=spec.weighting,
            neutralization=spec.neutralization,
        )
        factors_ranked = {name: rank_scores(rows) for name, rows in prepared.items()}
        return {
            "strategy": spec.model_dump(mode="json"),
            "ranking": [row.__dict__ for row in ranked],
            "weights": weights,
            "evaluation": evaluate_factor(ranked, forward_returns),
            "factor_exposures": factor_exposures(weights, factors_ranked),
            "robustness_flags": robustness_flags(ranked, weights),
        }
