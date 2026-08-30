from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.ml_research.schemas import MLExperimentDefinition, MLObservation


class MLRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    definition: MLExperimentDefinition
    observations: list[MLObservation] = Field(min_length=1)


class MLDriftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observed_at: datetime
    window_start: datetime
    window_end: datetime
    sample_count: int = Field(ge=1)
    source: str = Field(min_length=1, max_length=64)
    baseline: dict[str, Any]
    observed: dict[str, Any]

    @model_validator(mode="after")
    def valid_window(self) -> MLDriftRequest:
        if self.window_start >= self.window_end:
            raise ValueError("drift window start must precede end")
        return self


class MLRetrainRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trigger: str
    definition: MLExperimentDefinition
    observations: list[MLObservation] = Field(min_length=1)


class MLOosMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_count: int = Field(ge=0)
    ic: float
    rank_ic: float
    sharpe: float
    max_drawdown: float


class MLPromotionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    champion_model_id: UUID | None = None
    candidate_oos: MLOosMetrics
    champion_oos: MLOosMetrics | None = None
    stress_passed: bool
    regime_passed: bool
    stress_summary: dict[str, Any] = Field(default_factory=dict)
    regime_summary: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def comparison_has_champion_evidence(self) -> MLPromotionRequest:
        if self.champion_model_id is not None and self.champion_oos is None:
            raise ValueError("champion_oos is required when a champion model is supplied")
        return self
