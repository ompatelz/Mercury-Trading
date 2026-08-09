from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class ResearchExperimentRequest(BaseModel):
    objective: str = Field(min_length=10, max_length=1000)
    symbol: str = Field(min_length=1, max_length=32)
    start_date: date
    end_date: date
    interval: str = "1d"
    initial_capital: float = Field(default=10_000.0, gt=0)
    transaction_cost_bps: float = Field(default=1.0, ge=0)
    slippage_bps: float = Field(default=0.0, ge=0)
    execution_engine: str = "python"

    @model_validator(mode="after")
    def validate_dates(self) -> "ResearchExperimentRequest":
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")
        return self


class HypothesisOutput(BaseModel):
    hypothesis: str = Field(min_length=10)
    rationale: str = Field(min_length=10)
    symbol: str = Field(min_length=1, max_length=32)
    strategy_family: str = Field(min_length=1)
    parameters_to_test: dict[str, Any]
    expected_behavior: str = Field(min_length=10)
    failure_conditions: list[str] = Field(min_length=1)


class StrategySpecification(BaseModel):
    strategy: str = Field(min_length=1)
    symbol: str = Field(min_length=1, max_length=32)
    parameters: dict[str, Any]


class BacktestToolResult(BaseModel):
    experiment_id: UUID
    metrics: dict[str, Any]
    dataset: dict[str, Any]
    strategy: str
    parameters: dict[str, Any]
    execution_engine: str


class EvaluationOutput(BaseModel):
    measured_facts: list[str] = Field(min_length=1)
    risk_findings: list[str] = Field(min_length=1)
    interpretation: str = Field(min_length=10)
    limitations: list[str] = Field(min_length=1)


class CriticOutput(BaseModel):
    hypothesis_tested: bool
    parameter_assessment: str = Field(min_length=10)
    robustness_assessment: str = Field(min_length=10)
    methodological_weaknesses: list[str] = Field(min_length=1)
    lesson: str = Field(min_length=10)
    suggested_next_experiment: str = Field(min_length=10)


class ResearchReport(BaseModel):
    research_objective: str
    hypothesis: str
    strategy_tested: str
    parameters: dict[str, Any]
    dataset: dict[str, Any]
    performance_metrics: dict[str, Any]
    measured_facts: list[str]
    risk_findings: list[str]
    critic_findings: CriticOutput
    conclusion: str
    suggested_next_experiment: str


class ModelInvocationMetadata(BaseModel):
    provider: str
    model: str
    temperature: float | None = None
    prompt_versions: dict[str, str]
    model_calls: int = 0
    token_usage: dict[str, int] = Field(default_factory=dict)
    estimated_cost: float | None = None
    latency_ms: float = 0.0


class ResearchExperimentResponse(BaseModel):
    id: UUID
    objective: str
    symbol: str
    start_date: date
    end_date: date
    interval: str
    execution_engine: str
    status: str
    hypothesis: dict[str, Any]
    strategy: dict[str, Any]
    backtest_experiment_id: UUID | None
    metrics: dict[str, Any]
    evaluation: dict[str, Any]
    critique: dict[str, Any]
    report: dict[str, Any]
    model_metadata: dict[str, Any]
    workflow_metadata: dict[str, Any]
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
