from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ProductionSimulationCreateRequest(BaseModel):
    universe: list[str] = Field(min_length=1)
    start_date: date
    end_date: date
    research_window_days: int = Field(default=30, gt=0)
    deployment_window_days: int = Field(default=30, gt=0)
    cadence_days: int | None = Field(default=None, gt=0)
    initial_capital: float = Field(default=10_000, gt=0)
    strategy_parameters: dict[str, int] = Field(
        default_factory=lambda: {"fast_window": 2, "slow_window": 5}
    )
    strategy_version: str = "moving_average_crossover:v1"
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    portfolio_weights: dict[str, float] = Field(default_factory=dict)
    execution: dict[str, Any] = Field(default_factory=dict)
    data_versions: dict[str, Any] = Field(default_factory=dict)
    max_drawdown: float = Field(default=1.0, gt=0, le=1)
    kill_action: str = "PAUSE"

    @model_validator(mode="after")
    def validate_dates(self) -> "ProductionSimulationCreateRequest":
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")
        if self.kill_action not in {"PAUSE", "STOP", "FALLBACK_TO_CASH"}:
            raise ValueError("kill_action must be PAUSE, STOP, or FALLBACK_TO_CASH")
        for candidate in self.candidates:
            if "version" not in candidate or "parameters" not in candidate:
                raise ValueError("each candidate requires version and parameters")
        return self


class ProductionSimulationResponse(BaseModel):
    id: UUID
    universe: list[str]
    start_date: date
    end_date: date
    research_window_days: int
    deployment_window_days: int
    cadence_days: int
    initial_capital: float
    execution_model: dict[str, Any]
    data_versions: dict[str, Any]
    strategy_versions: list[str]
    configuration: dict[str, Any]
    status: str
    timeline: list[dict[str, Any]]
    metrics: dict[str, Any]
    error_message: str | None

    model_config = {"from_attributes": True}
