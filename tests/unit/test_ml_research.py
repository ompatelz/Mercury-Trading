from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.factor_research.engine import construct_weights, rank_scores
from app.ml_research.integration import predictions_to_score_points
from app.ml_research.schemas import MLExperimentDefinition, MLObservation, Period
from app.ml_research.service import MLResearchService
from app.models.ml import MLModel, MLPrediction


def _definition() -> MLExperimentDefinition:
    start = datetime(2020, 1, 1, tzinfo=UTC)
    return MLExperimentDefinition(
        experiment_key="linear-alpha-v1",
        model_type="linear_regression",
        task_type="cross_sectional_regression",
        target="forward_return",
        feature_names=("momentum", "volatility"),
        feature_versions=({"momentum": "v1"},),
        universe=("AAA", "BBB"),
        train=Period(start=start, end=start + timedelta(days=4)),
        validation=Period(start=start + timedelta(days=4), end=start + timedelta(days=6)),
        test=Period(start=start + timedelta(days=6), end=start + timedelta(days=8)),
        dataset_fingerprint="a" * 64,
    )


def _rows() -> list[MLObservation]:
    start = datetime(2020, 1, 1, tzinfo=UTC)
    return [
        MLObservation(
            timestamp=start + timedelta(days=day),
            available_at=start + timedelta(days=day),
            target_timestamp=start + timedelta(days=day + 1),
            asset_id=asset,
            features={"momentum": float(day + sign), "volatility": float(sign + 2)},
            target=float(day + sign) / 100,
        )
        for day in range(8)
        for asset, sign in (("AAA", 1), ("BBB", 2))
    ]


def test_rejects_future_feature_availability() -> None:
    timestamp = datetime(2020, 1, 1, tzinfo=UTC)
    with pytest.raises(ValueError, match="not available"):
        MLObservation(
            timestamp=timestamp,
            available_at=timestamp + timedelta(seconds=1),
            target_timestamp=timestamp + timedelta(days=1),
            asset_id="AAA",
            features={"momentum": 1.0},
            target=0.1,
        )


def test_pipeline_fits_preprocessing_on_training_only_and_persists_lineage(
    db_session: Session, tmp_path: Path
) -> None:
    result = MLResearchService(tmp_path).run(_definition(), _rows())
    assert result["test"]["count"] == 4.0
    assert result["artifact"]["preprocessing"]["means"] != [0.0, 0.0]
    model = MLResearchService(tmp_path).persist(db_session, _definition(), result)
    assert Path(model.artifact_location).is_file()
    assert db_session.query(MLModel).count() == 1
    assert db_session.query(MLPrediction).count() == 4


def test_predictions_adapt_to_factor_score_contract() -> None:
    result = MLResearchService().run(_definition(), _rows())
    score_points = predictions_to_score_points(result["predictions"])
    weights = construct_weights(rank_scores(score_points), selection="top_n", top_n=1)
    assert {weight["timestamp"] for weight in weights} == {
        point.timestamp.isoformat() for point in score_points
    }
    assert all(abs(float(weight["weight"])) == 1.0 for weight in weights)


def test_splits_are_chronological() -> None:
    start = datetime(2020, 1, 1, tzinfo=UTC)
    with pytest.raises(ValueError, match="chronological"):
        MLExperimentDefinition(
            experiment_key="bad",
            model_type="historical_mean",
            task_type="time_series_regression",
            target="next_return",
            feature_names=("x",),
            feature_versions=({"x": "v1"},),
            universe=("AAA",),
            train=Period(start=start, end=start + timedelta(days=2)),
            validation=Period(start=start + timedelta(days=1), end=start + timedelta(days=3)),
            test=Period(start=start + timedelta(days=3), end=start + timedelta(days=4)),
            dataset_fingerprint="b" * 64,
        )
