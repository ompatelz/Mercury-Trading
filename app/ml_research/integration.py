from __future__ import annotations

from typing import Any

from app.factor_research.schemas import ScorePoint


def predictions_to_score_points(predictions: list[dict[str, Any]]) -> list[ScorePoint]:
    """Adapt persisted ML predictions into the factor ranking contract."""
    return [
        ScorePoint(
            timestamp=item["timestamp"],
            asset_id=str(item["asset_id"]),
            score=float(item["score"]),
        )
        for item in predictions
    ]
