from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class HealthState(StrEnum):
    HEALTHY = "HEALTHY"
    WATCH = "WATCH"
    DEGRADED = "DEGRADED"
    SUSPENDED = "SUSPENDED"
    RETIRED = "RETIRED"


class LifecycleState(StrEnum):
    RESEARCHED = "RESEARCHED"
    VALIDATED = "VALIDATED"
    PROMOTED = "PROMOTED"
    ACTIVE = "ACTIVE"
    MONITORED = "MONITORED"
    RETAIN = "RETAIN"
    INVESTIGATE = "INVESTIGATE"
    DE_RISK = "DE_RISK"
    RETIRE = "RETIRE"


class HealthObservationRequest(BaseModel):
    observed_at: datetime
    source: str = "PAPER"
    metrics: dict[str, float] = Field(min_length=1)
    expected_metrics: dict[str, float] = Field(default_factory=dict)
    regime_context: dict[str, Any] = Field(default_factory=dict)
    execution_context: dict[str, float] = Field(default_factory=dict)


class ResearchScheduleRequest(BaseModel):
    strategy_id: UUID | None = None
    mode: str
    cadence_days: int | None = Field(default=None, ge=1)
    campaign_template: dict[str, Any]
    trigger_types: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_mode(self) -> "ResearchScheduleRequest":
        if self.mode not in {"PERIODIC", "EVENT_TRIGGERED", "HYBRID"}:
            raise ValueError("mode must be PERIODIC, EVENT_TRIGGERED, or HYBRID")
        if self.mode in {"PERIODIC", "HYBRID"} and self.cadence_days is None:
            raise ValueError("cadence_days is required for periodic scheduling")
        return self


class StrategyHealthResponse(BaseModel):
    strategy_id: UUID
    state: str
    lifecycle_state: str
    latest_score: float
    latest_components: dict[str, Any]
    active_flags: list[str]
    last_evaluated_at: datetime

    model_config = {"from_attributes": True}


class StrategyHealthTimelineResponse(BaseModel):
    health: StrategyHealthResponse | None
    observations: list[dict[str, Any]]
    decisions: list[dict[str, Any]]
    triggers: list[dict[str, Any]]
