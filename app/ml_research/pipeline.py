"""Pure temporal ML pipeline. It intentionally owns no market or portfolio state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from app.ml_research.schemas import MLExperimentDefinition, MLObservation, Period

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class FittedPreprocessor:
    names: tuple[str, ...]
    means: FloatArray
    scales: FloatArray

    def transform(self, rows: list[MLObservation]) -> FloatArray:
        matrix = feature_matrix(rows, self.names)
        return np.asarray((matrix - self.means) / self.scales, dtype=np.float64)


@dataclass(frozen=True)
class FittedModel:
    algorithm: str
    coefficients: FloatArray
    intercept: float

    def predict(self, values: FloatArray) -> FloatArray:
        raw = values @ self.coefficients + self.intercept
        if self.algorithm == "logistic_regression":
            return np.asarray(1.0 / (1.0 + np.exp(-np.clip(raw, -30, 30))), dtype=np.float64)
        return np.asarray(raw, dtype=np.float64)


def split_observations(
    definition: MLExperimentDefinition, rows: list[MLObservation]
) -> tuple[list[MLObservation], list[MLObservation], list[MLObservation]]:
    _validate_rows(definition, rows)
    return (
        _in_period(rows, definition.train),
        _in_period(rows, definition.validation),
        _in_period(rows, definition.test),
    )


def fit_preprocessor(rows: list[MLObservation], names: tuple[str, ...]) -> FittedPreprocessor:
    if not rows:
        raise ValueError("training split is empty")
    matrix = feature_matrix(rows, names)
    means = matrix.mean(axis=0)
    scales = matrix.std(axis=0)
    return FittedPreprocessor(names, means, np.where(scales == 0, 1.0, scales))


def fit_model(
    algorithm: Literal["historical_mean", "linear_regression", "logistic_regression"],
    values: FloatArray,
    targets: FloatArray,
    *,
    regularization: float = 1e-6,
) -> FittedModel:
    if algorithm == "historical_mean":
        return FittedModel(
            algorithm,
            np.zeros(values.shape[1], dtype=np.float64),
            float(targets.mean()),
        )
    design = np.column_stack((np.ones(len(values)), values))
    if algorithm == "linear_regression":
        penalty = np.eye(design.shape[1]) * regularization
        penalty[0, 0] = 0.0
        weights = np.linalg.solve(design.T @ design + penalty, design.T @ targets)
        return FittedModel(algorithm, weights[1:], float(weights[0]))
    weights = np.zeros(design.shape[1])
    rate = 0.1
    for _ in range(300):
        probability = 1.0 / (1.0 + np.exp(-np.clip(design @ weights, -30, 30)))
        gradient = design.T @ (probability - targets) / len(targets)
        gradient[1:] += regularization * weights[1:]
        weights -= rate * gradient
    return FittedModel(algorithm, weights[1:], float(weights[0]))


def feature_matrix(rows: list[MLObservation], names: tuple[str, ...]) -> FloatArray:
    missing = sorted({name for row in rows for name in names if name not in row.features})
    if missing:
        raise ValueError(f"observations missing declared features: {missing}")
    matrix = np.array([[row.features[name] for name in names] for row in rows], dtype=np.float64)
    if not np.isfinite(matrix).all():
        raise ValueError("features must be finite")
    return matrix


def _in_period(rows: list[MLObservation], period: Period) -> list[MLObservation]:
    return [row for row in rows if period.start <= row.timestamp < period.end]


def _validate_rows(definition: MLExperimentDefinition, rows: list[MLObservation]) -> None:
    if not rows:
        raise ValueError("ML experiment has no observations")
    unknown = sorted({row.asset_id for row in rows if row.asset_id not in definition.universe})
    if unknown:
        raise ValueError(f"observations outside experiment universe: {unknown}")
