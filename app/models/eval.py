import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    benchmark_name: Mapped[str] = mapped_column(String(100), nullable=False)
    benchmark_version: Mapped[str] = mapped_column(String(32), default="v1", nullable=False)
    workflow_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_versions.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    aggregate_metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    execution_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EvalTaskResult(Base):
    __tablename__ = "eval_task_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    eval_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("eval_runs.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[str] = mapped_column(String(100), nullable=False)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    success: Mapped[bool] = mapped_column(nullable=False)
    scores: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    findings: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    latency_ms: Mapped[float] = mapped_column(nullable=False)
    output: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    token_usage: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    estimated_cost: Mapped[float] = mapped_column(default=0.0, nullable=False)
    failure_type: Mapped[str | None] = mapped_column(String(100), nullable=True)


class WorkflowExperiment(Base):
    __tablename__ = "workflow_experiments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    baseline_workflow_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_versions.id"), nullable=False
    )
    candidate_workflow_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_versions.id"), nullable=False
    )
    benchmark_name: Mapped[str] = mapped_column(String(100), nullable=False)
    benchmark_version: Mapped[str] = mapped_column(String(32), nullable=False)
    baseline_eval_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("eval_runs.id"), nullable=False
    )
    candidate_eval_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("eval_runs.id"), nullable=False
    )
    promotion_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    comparison: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class WorkflowCandidateChange(Base):
    __tablename__ = "workflow_candidate_changes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workflow_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_versions.id"), nullable=False
    )
    change_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_failure: Mapped[str] = mapped_column(Text, nullable=False)
    changes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
