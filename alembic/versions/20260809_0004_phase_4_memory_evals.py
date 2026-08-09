"""Add Phase 4 memory, eval, and versioning records.

Revision ID: 20260809_0004
Revises: 20260809_0003
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260809_0004"
down_revision: str | None = "20260809_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=32), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("name", "version", name="uq_agent_versions_name_version"),
    )
    op.create_table(
        "workflow_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("backtester_version", sa.String(length=32), nullable=False),
        sa.Column("retrieval_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("tool_versions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("name", "version", name="uq_workflow_versions_name_version"),
    )
    op.add_column("research_experiments", sa.Column("agent_version_id", sa.Uuid(), nullable=True))
    op.add_column(
        "research_experiments", sa.Column("workflow_version_id", sa.Uuid(), nullable=True)
    )
    op.create_foreign_key(
        "fk_research_experiments_agent_version",
        "research_experiments",
        "agent_versions",
        ["agent_version_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_research_experiments_workflow_version",
        "research_experiments",
        "workflow_versions",
        ["workflow_version_id"],
        ["id"],
    )
    op.create_table(
        "research_memory_lessons",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("research_experiment_id", sa.Uuid(), nullable=False),
        sa.Column("backtest_experiment_id", sa.Uuid(), nullable=True),
        sa.Column("hypothesis", sa.Text(), nullable=False),
        sa.Column("strategy_family", sa.String(length=100), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("asset_class", sa.String(length=32), nullable=False),
        sa.Column("market_regime", sa.String(length=100), nullable=False),
        sa.Column("period_start", sa.String(length=16), nullable=False),
        sa.Column("period_end", sa.String(length=16), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("risk_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("failure_reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("critic_summary", sa.Text(), nullable=False),
        sa.Column("observations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("embedding", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("agent_version", sa.String(length=64), nullable=False),
        sa.Column("workflow_version", sa.String(length=64), nullable=False),
        sa.Column("failure_type", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["backtest_experiment_id"], ["experiments.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["research_experiment_id"], ["research_experiments.id"], ondelete="CASCADE"
        ),
    )
    op.create_index(
        "ix_memory_strategy_regime",
        "research_memory_lessons",
        ["strategy_family", "market_regime"],
    )
    op.create_index(
        "ix_memory_symbol_failure",
        "research_memory_lessons",
        ["symbol", "failure_type"],
    )
    op.create_table(
        "research_trace_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("research_experiment_id", sa.Uuid(), nullable=False),
        sa.Column("workflow_run_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("event_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["research_experiment_id"], ["research_experiments.id"], ondelete="CASCADE"
        ),
    )
    op.create_table(
        "eval_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("benchmark_name", sa.String(length=100), nullable=False),
        sa.Column("workflow_version_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("aggregate_metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["workflow_version_id"], ["workflow_versions.id"]),
    )
    op.create_table(
        "eval_task_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("eval_run_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.String(length=100), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("scores", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("findings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["eval_run_id"], ["eval_runs.id"], ondelete="CASCADE"),
    )
    op.create_table(
        "version_comparisons",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("baseline_workflow_version_id", sa.Uuid(), nullable=False),
        sa.Column("candidate_workflow_version_id", sa.Uuid(), nullable=False),
        sa.Column("benchmark_name", sa.String(length=100), nullable=False),
        sa.Column("metric_differences", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["baseline_workflow_version_id"], ["workflow_versions.id"]),
        sa.ForeignKeyConstraint(["candidate_workflow_version_id"], ["workflow_versions.id"]),
    )


def downgrade() -> None:
    op.drop_table("version_comparisons")
    op.drop_table("eval_task_results")
    op.drop_table("eval_runs")
    op.drop_table("research_trace_events")
    op.drop_index("ix_memory_symbol_failure", table_name="research_memory_lessons")
    op.drop_index("ix_memory_strategy_regime", table_name="research_memory_lessons")
    op.drop_table("research_memory_lessons")
    op.drop_constraint(
        "fk_research_experiments_workflow_version", "research_experiments", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_research_experiments_agent_version", "research_experiments", type_="foreignkey"
    )
    op.drop_column("research_experiments", "workflow_version_id")
    op.drop_column("research_experiments", "agent_version_id")
    op.drop_table("workflow_versions")
    op.drop_table("agent_versions")
