from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.factor_research.engine import construct_weights, rank_scores
from app.ml_research.integration import predictions_to_score_points
from app.ml_research.lifecycle import MLModelLifecycleService
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


def _persist_model(db_session: Session, tmp_path: Path, key: str) -> MLModel:
    definition = MLExperimentDefinition.model_validate(
        {**_definition().model_dump(), "experiment_key": key}
    )
    service = MLResearchService(tmp_path)
    model = service.persist(db_session, definition, service.run(definition, _rows()))
    model.status = "VALIDATED"
    db_session.flush()
    return model


def _drift_values(fingerprint: str = "a" * 64) -> dict[str, object]:
    return {
        "dataset_fingerprint": fingerprint,
        "feature_means": {"momentum": 0.0},
        "prediction_mean": 0.0,
        "ic": 0.2,
        "rank_ic": 0.2,
        "portfolio_sharpe": 1.0,
        "feature_importance": {"momentum": 0.2},
        "regime_metrics": {"bull": {"ic": 0.2}},
    }


def test_drift_requires_minimum_evidence_and_persistence(
    db_session: Session, tmp_path: Path
) -> None:
    model = _persist_model(db_session, tmp_path, "drift-model")
    service = MLModelLifecycleService(db_session)
    start = datetime(2021, 1, 1, tzinfo=UTC)
    baseline = _drift_values()
    observed = {**_drift_values("b" * 64), "prediction_mean": 1.0}
    insufficient = service.record_drift(
        model.id,
        observed_at=start,
        window_start=start,
        window_end=start + timedelta(days=1),
        sample_count=5,
        source="shadow",
        baseline=baseline,
        observed=observed,
    )
    assert insufficient.drift_types == []
    assert not insufficient.retraining_triggered
    first = service.record_drift(
        model.id,
        observed_at=start + timedelta(days=2),
        window_start=start + timedelta(days=1),
        window_end=start + timedelta(days=2),
        sample_count=30,
        source="shadow",
        baseline=baseline,
        observed=observed,
    )
    second = service.record_drift(
        model.id,
        observed_at=start + timedelta(days=3),
        window_start=start + timedelta(days=2),
        window_end=start + timedelta(days=3),
        sample_count=30,
        source="shadow",
        baseline=baseline,
        observed=observed,
    )
    assert {"DATA_DRIFT", "PREDICTION_DRIFT"} <= set(first.drift_types)
    assert not first.retraining_triggered
    assert second.consecutive_windows == 2
    assert second.retraining_triggered


def test_retraining_creates_only_a_lineaged_research_candidate(
    db_session: Session, tmp_path: Path
) -> None:
    parent = _persist_model(db_session, tmp_path, "parent-model")
    definition = MLExperimentDefinition.model_validate(
        {**_definition().model_dump(), "experiment_key": "retrained-model"}
    )
    candidate = MLModelLifecycleService(db_session, MLResearchService(tmp_path)).retrain(
        parent.id, definition, _rows(), "SCHEDULED"
    )
    assert candidate.parent_model_id == parent.id
    assert candidate.status != "CHAMPION"
    assert candidate.lifecycle_metadata["deployment_state"] == "RESEARCH_ONLY"


def test_promotion_requires_oos_stress_and_regime_evidence(
    db_session: Session, tmp_path: Path
) -> None:
    champion = _persist_model(db_session, tmp_path, "champion-model")
    candidate = _persist_model(db_session, tmp_path, "candidate-model")
    service = MLModelLifecycleService(db_session)
    rejected = service.decide_promotion(
        champion.id,
        candidate.id,
        {
            "candidate_oos": {
                "sample_count": 30,
                "ic": 0.3,
                "rank_ic": 0.3,
                "sharpe": 1.2,
                "max_drawdown": -0.1,
            },
            "champion_oos": {
                "sample_count": 30,
                "ic": 0.2,
                "rank_ic": 0.2,
                "sharpe": 1.0,
                "max_drawdown": -0.1,
            },
            "stress_passed": False,
            "regime_passed": True,
        },
    )
    assert rejected.decision == "REJECT"
    assert candidate.status == "VALIDATED"
    promoted = service.decide_promotion(
        champion.id,
        candidate.id,
        {
            "candidate_oos": {
                "sample_count": 30,
                "ic": 0.3,
                "rank_ic": 0.3,
                "sharpe": 1.2,
                "max_drawdown": -0.1,
            },
            "champion_oos": {
                "sample_count": 30,
                "ic": 0.2,
                "rank_ic": 0.2,
                "sharpe": 1.0,
                "max_drawdown": -0.1,
            },
            "stress_passed": True,
            "regime_passed": True,
        },
    )
    assert promoted.decision == "PROMOTE"
    assert champion.status == "SUPERSEDED"
    assert candidate.status == "CHAMPION"
