from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class EvolutionRunCreateRequest(BaseModel):
    objective: str = Field(min_length=10)
    symbol: str = Field(min_length=1, max_length=32)
    start: date
    end: date
    interval: str = "1d"
    initial_population: list[dict[str, int]] = Field(
        default_factory=lambda: [
            {"short_window": 5, "long_window": 20},
            {"short_window": 10, "long_window": 30},
            {"short_window": 15, "long_window": 45},
        ]
    )
    generations: int = Field(default=2, ge=1, le=10)
    population_size: int = Field(default=3, ge=2, le=20)
    memory_enabled: bool = False
    transaction_cost_bps: float = Field(default=1.0, ge=0.0)
    slippage_bps: float = Field(default=0.0, ge=0.0)

    @model_validator(mode="after")
    def validate_dates(self) -> "EvolutionRunCreateRequest":
        if self.start >= self.end:
            raise ValueError("start must be before end")
        return self


class StrategyCandidateResponse(BaseModel):
    id: UUID
    evolution_run_id: UUID
    parent_strategy_ids: list[str]
    generation: int
    strategy_specification: dict[str, Any]
    mutation_type: str | None
    changed_fields: list[str]
    fitness: dict[str, Any]
    regime_performance: dict[str, Any]
    diversity: dict[str, Any]
    status: str
    rejection_reason: str | None
    promotion_status: str
    memory_ids: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class EvolutionRunResponse(BaseModel):
    id: UUID
    objective: str
    symbol: str
    interval: str
    status: str
    settings: dict[str, Any]
    metrics: dict[str, Any]
    memory_enabled: bool
    memory_provenance: list[dict[str, Any]]
    report: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
