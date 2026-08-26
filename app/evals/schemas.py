from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.evals.benchmarks import DEFAULT_BENCHMARK_NAME


class EvalRunRequest(BaseModel):
    benchmark_name: str = DEFAULT_BENCHMARK_NAME
    workflow_version_id: UUID | None = None


class EvalTaskResultResponse(BaseModel):
    task_id: str
    task_type: str
    success: bool
    scores: dict[str, Any]
    findings: list[str]
    latency_ms: float

    model_config = {"from_attributes": True}


class EvalRunResponse(BaseModel):
    id: UUID
    benchmark_name: str
    workflow_version_id: UUID
    status: str
    aggregate_metrics: dict[str, Any]
    benchmark_version: str
    execution_metadata: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class VersionComparisonRequest(BaseModel):
    baseline_eval_run_id: UUID
    candidate_eval_run_id: UUID
    min_task_success_delta: float = Field(default=0.0)
    max_latency_increase_pct: float = Field(default=0.25, ge=0)


class VersionComparisonResponse(BaseModel):
    id: UUID
    baseline_workflow_version_id: UUID
    candidate_workflow_version_id: UUID
    benchmark_name: str
    metric_differences: dict[str, Any]
    decision: str
    reason: str
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkflowExperimentRequest(BaseModel):
    baseline_workflow_version_id: UUID
    candidate_workflow_version_id: UUID
    benchmark_name: str = DEFAULT_BENCHMARK_NAME
    promotion_rules: dict[str, Any] = Field(default_factory=dict)


class WorkflowExperimentResponse(BaseModel):
    id: UUID
    baseline_workflow_version_id: UUID
    candidate_workflow_version_id: UUID
    benchmark_name: str
    benchmark_version: str
    baseline_eval_run_id: UUID
    candidate_eval_run_id: UUID
    promotion_config: dict[str, Any]
    comparison: dict[str, Any]
    decision: str
    reason: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BenchmarkResponse(BaseModel):
    name: str
    version: str
    tasks: list[dict[str, Any]]


class ChampionResponse(BaseModel):
    component: str
    workflow_version_id: UUID
    promoted_from_experiment_id: UUID | None
