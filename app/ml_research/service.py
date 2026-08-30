from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import UUID

import numpy as np
from numpy.typing import NDArray
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.governance.service import DecisionService
from app.ml_research.pipeline import feature_matrix, fit_model, fit_preprocessor, split_observations
from app.ml_research.schemas import MLExperimentDefinition, MLObservation
from app.models.ml import MLModel, MLPrediction
from app.research_artifacts.fingerprints import stable_hash

FloatArray = NDArray[np.float64]
Transform = Callable[[list[MLObservation]], FloatArray]


class MLResearchService:
    def __init__(self, artifact_root: Path | None = None) -> None:
        self.artifact_root = artifact_root or get_settings().data_storage_root / "ml-artifacts"

    def run(self, definition: MLExperimentDefinition, rows: list[MLObservation]) -> dict[str, Any]:
        train, validation, test = split_observations(definition, rows)
        preprocessor = fit_preprocessor(train, definition.feature_names)
        transform: Transform
        if definition.preprocessing == "none":

            def transform(values: list[MLObservation]) -> FloatArray:
                return feature_matrix(values, definition.feature_names)
        else:
            transform = preprocessor.transform
        train_values = transform(train)
        model = fit_model(
            definition.model_type,
            train_values,
            np.array([row.target for row in train], dtype=np.float64),
            regularization=float(definition.hyperparameters.get("regularization", 1e-6)),
        )
        results: dict[str, Any] = {"train": _metrics(train, model.predict(train_values))}
        for name, split in (("validation", validation), ("test", test)):
            values = transform(split)
            results[name] = _metrics(split, model.predict(values))
        results["overfitting_flags"] = _overfitting_flags(results)
        results["feature_importance"] = {
            name: round(float(value), 10)
            for name, value in zip(definition.feature_names, model.coefficients, strict=True)
        }
        results["predictions"] = [
            {
                "timestamp": row.timestamp,
                "asset_id": row.asset_id,
                "prediction": float(value),
                "score": float(value),
            }
            for row, value in zip(test, model.predict(transform(test)), strict=True)
        ]
        results["artifact"] = {
            "algorithm": model.algorithm,
            "coefficients": model.coefficients.tolist(),
            "intercept": model.intercept,
            "preprocessing": {
                "means": preprocessor.means.tolist(),
                "scales": preprocessor.scales.tolist(),
            },
        }
        return results

    def persist(
        self,
        session: Session,
        definition: MLExperimentDefinition,
        result: dict[str, Any],
        *,
        parent_model_id: UUID | None = None,
        lifecycle_metadata: dict[str, Any] | None = None,
    ) -> MLModel:
        artifact = dict(result["artifact"])
        checksum = stable_hash(artifact)
        artifact_path = self.artifact_root / definition.experiment_key / f"{checksum}.json"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(json.dumps(artifact, sort_keys=True), encoding="utf-8")
        model = MLModel(
            model_key=definition.experiment_key,
            algorithm=definition.model_type,
            status="VALIDATED" if not result["overfitting_flags"] else "CANDIDATE",
            dataset_fingerprint=definition.dataset_fingerprint,
            feature_versions=list(definition.feature_versions),
            definition=definition.model_dump(mode="json"),
            metrics={
                key: value
                for key, value in result.items()
                if key not in {"predictions", "artifact"}
            },
            artifact_location=str(artifact_path),
            artifact_checksum=checksum,
            parent_model_id=parent_model_id,
            lifecycle_metadata=lifecycle_metadata or {"deployment_state": "RESEARCH_ONLY"},
        )
        session.add(model)
        session.flush()
        prediction_rows = [
            MLPrediction(
                model_id=model.id,
                feature_fingerprint=definition.dataset_fingerprint,
                **item,
            )
            for item in result["predictions"]
        ]
        session.add_all(prediction_rows)
        DecisionService(session).record(
            decision_type="MODEL_VALIDATED",
            outcome=model.status,
            actor="ml_research_service",
            reason="temporal ML candidate evaluated against held-out test data",
            rules=[{"rule": flag, "passed": False} for flag in result["overfitting_flags"]],
            inputs={
                "model_key": definition.experiment_key,
                "dataset_fingerprint": definition.dataset_fingerprint,
            },
            metrics=result["test"],
            versions={"model_version": definition.model_version},
        )
        return model


def _metrics(rows: list[MLObservation], predictions: FloatArray) -> dict[str, float]:
    if not rows:
        return {"count": 0.0, "mae": 0.0, "mse": 0.0, "r2": 0.0, "ic": 0.0, "rank_ic": 0.0}
    actual = np.array([row.target for row in rows], dtype=np.float64)
    error = actual - predictions
    variance = float(((actual - actual.mean()) ** 2).sum())
    correlation = _corr(actual, predictions)
    ranks = _rank_ic(rows, predictions)
    return {
        "count": float(len(rows)),
        "mae": float(np.abs(error).mean()),
        "mse": float((error**2).mean()),
        "r2": 0.0 if variance == 0 else float(1 - (error**2).sum() / variance),
        "ic": correlation,
        "rank_ic": ranks,
    }


def _rank_ic(rows: list[MLObservation], predictions: FloatArray) -> float:
    grouped: dict[object, list[tuple[float, float]]] = defaultdict(list)
    for row, prediction in zip(rows, predictions, strict=True):
        grouped[row.timestamp].append((float(prediction), row.target))
    values = [
        _corr(
            np.asarray(np.argsort(np.argsort([x[0] for x in pair])), dtype=np.float64),
            np.asarray(np.argsort(np.argsort([x[1] for x in pair])), dtype=np.float64),
        )
        for pair in grouped.values()
        if len(pair) > 1
    ]
    return float(np.mean(values)) if values else 0.0


def _corr(left: FloatArray, right: FloatArray) -> float:
    if len(left) < 2 or np.std(left) == 0 or np.std(right) == 0:
        return 0.0
    return float(np.corrcoef(left, right)[0, 1])


def _overfitting_flags(results: dict[str, Any]) -> list[str]:
    train, validation, test = results["train"], results["validation"], results["test"]
    flags: list[str] = []
    if train["r2"] - validation["r2"] > 0.25:
        flags.append("TRAIN_VALIDATION_GAP_HIGH")
    if test["ic"] < 0:
        flags.append("LOW_OOS_IC")
    if abs(validation["rank_ic"] - test["rank_ic"]) > 0.4:
        flags.append("FEATURE_INSTABILITY")
    return flags
