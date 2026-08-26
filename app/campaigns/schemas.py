from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class CampaignCreateRequest(BaseModel):
    objective: str = Field(min_length=10)
    symbols: list[str] = Field(min_length=1)
    start_date: date
    end_date: date
    interval: str = "1d"
    constraints: dict[str, Any] = Field(default_factory=dict)
    datasets: dict[str, Any] = Field(default_factory=dict)
    split_definition: dict[str, dict[str, str]] | None = None
    budget: dict[str, Any] = Field(
        default_factory=lambda: {
            "max_experiments": 12,
            "max_optimization_trials": 12,
            "max_llm_calls": 0,
            "max_runtime_seconds": 600,
            "max_api_cost": 0.0,
        }
    )
    parameter_space: dict[str, Any] | None = None
    optimization_method: str = "grid"
    optimization_seed: int = 17
    stop_conditions: dict[str, Any] = Field(
        default_factory=lambda: {
            "no_improvement_rounds": 2,
            "minimum_score": 70.0,
            "candidate_robustness_threshold": 65.0,
        }
    )

    @model_validator(mode="after")
    def validate_period(self) -> "CampaignCreateRequest":
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")
        if self.optimization_method not in {"grid", "random", "bayesian"}:
            raise ValueError("optimization_method must be grid, random, or bayesian")
        return self


class CampaignRunRequest(BaseModel):
    batch_size: int | None = Field(default=None, ge=1)


class WorkerRunRequest(BaseModel):
    worker_name: str = "api-worker"
    max_jobs: int = Field(default=1, ge=1, le=100)


class OptimizationStudyCreateRequest(BaseModel):
    objective: str = Field(min_length=10)
    symbols: list[str] = Field(min_length=1)
    start_date: date
    end_date: date
    parameter_space: dict[str, Any]
    search_method: str = "grid"
    trial_budget: int = Field(default=12, ge=1, le=500)
    interval: str = "1d"
    constraints: dict[str, Any] = Field(default_factory=dict)
    split_definition: dict[str, dict[str, str]] | None = None
    random_seed: int = 17

    @model_validator(mode="after")
    def validate_study(self) -> "OptimizationStudyCreateRequest":
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")
        if self.search_method not in {"grid", "random", "bayesian"}:
            raise ValueError("search_method must be grid, random, or bayesian")
        return self


class OptimizationTrialResponse(BaseModel):
    id: UUID
    campaign_experiment_id: UUID
    experiment_id: UUID | None
    trial_number: int
    parameters: dict[str, Any]
    status: str
    rejection_reasons: list[str]
    objective_components: dict[str, Any]
    score: float | None
    sensitivity: dict[str, Any]
    engine: str | None
    engine_version: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class OptimizationStudyResponse(BaseModel):
    id: UUID
    campaign_id: UUID
    strategy_family: str
    parameter_space: dict[str, Any]
    objective_definition: dict[str, Any]
    dataset: dict[str, Any]
    validation_configuration: dict[str, Any]
    trial_budget: int
    search_method: str
    random_seed: int
    optimizer_metadata: dict[str, Any]
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CampaignResponse(BaseModel):
    id: UUID
    objective: str
    constraints: dict[str, Any]
    datasets: dict[str, Any]
    symbols: list[str]
    interval: str
    start_date: date
    end_date: date
    split_definition: dict[str, Any]
    budget: dict[str, Any]
    budget_used: dict[str, Any]
    status: str
    generated_hypotheses: list[dict[str, Any]]
    candidate_strategies: list[dict[str, Any]]
    rejected_strategies: list[dict[str, Any]]
    final_conclusions: dict[str, Any]
    stop_conditions: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CampaignExperimentResponse(BaseModel):
    id: UUID
    campaign_id: UUID
    experiment_id: UUID | None
    hypothesis: dict[str, Any]
    strategy_family: str
    parameters: dict[str, Any]
    symbol: str
    split_role: str
    status: str
    metrics: dict[str, Any]
    evaluation: dict[str, Any]
    risk_flags: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class CampaignJobResponse(BaseModel):
    id: UUID
    campaign_id: UUID
    campaign_experiment_id: UUID | None
    experiment_id: UUID | None
    job_type: str
    status: str
    payload: dict[str, Any]
    payload_version: int
    worker: str | None
    priority: int
    attempt_count: int
    max_attempts: int
    started_at: datetime | None
    ended_at: datetime | None
    heartbeat_at: datetime | None
    available_at: datetime
    cancel_requested: bool
    retry_history: list[dict[str, Any]]
    error_type: str | None
    error_message: str | None
    runtime_ms: float | None
    created_at: datetime

    model_config = {"from_attributes": True}


class QueueStatusResponse(BaseModel):
    jobs_queued: int
    jobs_running: int
    jobs_succeeded: int
    jobs_failed: int
    jobs_retrying: int
    jobs_cancelled: int


class WorkerStatusResponse(BaseModel):
    worker_id: str
    active_jobs: int
    last_heartbeat_at: datetime | None


class StrategyRankingResponse(BaseModel):
    id: UUID
    campaign_id: UUID
    campaign_experiment_id: UUID
    rank: int
    score: float
    component_scores: dict[str, Any]
    ranking_reason: str
    risk_flags: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class PortfolioEvaluationResponse(BaseModel):
    id: UUID
    campaign_id: UUID
    strategy_experiment_ids: list[str]
    weighting_method: str
    weights: dict[str, float]
    metrics: dict[str, Any]
    diversification_benefit: float
    correlation_matrix: dict[str, Any]
    definition: dict[str, Any]
    compatibility: dict[str, Any]
    rebalance_history: list[dict[str, Any]]
    incremental_benefit: dict[str, Any]
    rejection_reasons: list[str]
    ranking: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}
