from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MLObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    timestamp: datetime
    available_at: datetime
    target_timestamp: datetime
    asset_id: str = Field(min_length=1, max_length=64)
    features: dict[str, float]
    target: float

    @model_validator(mode="after")
    def point_in_time_contract(self) -> MLObservation:
        if self.available_at > self.timestamp:
            raise ValueError("feature is not available at prediction timestamp")
        if self.target_timestamp <= self.timestamp:
            raise ValueError("target timestamp must be strictly after prediction timestamp")
        return self


class Period(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    start: datetime
    end: datetime

    @model_validator(mode="after")
    def valid_range(self) -> Period:
        if self.start >= self.end:
            raise ValueError("period start must precede end")
        return self


class MLExperimentDefinition(BaseModel):
    """Full immutable recipe for a reproducible candidate, never an execution instruction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    experiment_key: str = Field(min_length=1, max_length=128)
    model_type: Literal["historical_mean", "linear_regression", "logistic_regression"]
    task_type: Literal["cross_sectional_regression", "time_series_regression", "classification"]
    target: Literal["next_return", "forward_return", "return_rank", "positive_return"]
    feature_names: tuple[str, ...] = Field(min_length=1)
    feature_versions: tuple[dict[str, str], ...] = Field(min_length=1)
    universe: tuple[str, ...] = Field(min_length=1)
    train: Period
    validation: Period
    test: Period
    dataset_fingerprint: str = Field(min_length=64, max_length=64)
    hyperparameters: dict[str, float | int | str | bool] = Field(default_factory=dict)
    preprocessing: Literal["standardize", "none"] = "standardize"
    random_seed: int = 7
    model_version: str = "ml-v1"

    @model_validator(mode="after")
    def temporal_ranges_do_not_overlap(self) -> MLExperimentDefinition:
        ranges_are_ordered = self.train.end <= self.validation.start
        ranges_are_ordered = ranges_are_ordered and self.validation.end <= self.test.start
        if not ranges_are_ordered:
            raise ValueError(
                "train, validation, and test periods must be chronological and non-overlapping"
            )
        return self
