"""Add Phase 5 research campaigns and persisted job queue.

Revision ID: 20260810_0005
Revises: 20260809_0004
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260810_0005"
down_revision: str | None = "20260809_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_campaigns",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("constraints", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("datasets", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("symbols", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("interval", sa.String(length=16), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("split_definition", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("budget", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("budget_used", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("generated_hypotheses", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("candidate_strategies", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rejected_strategies", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("final_conclusions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("stop_conditions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "campaign_experiments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("experiment_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("hypothesis", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("strategy_family", sa.String(length=100), nullable=False),
        sa.Column("parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("split_role", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evaluation", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("risk_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["campaign_id"], ["research_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], ondelete="SET NULL"),
        sa.UniqueConstraint(
            "campaign_id", "idempotency_key", name="uq_campaign_experiments_idempotency"
        ),
    )
    op.create_table(
        "campaign_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_experiment_id", sa.Uuid(), nullable=True),
        sa.Column("job_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("worker", sa.String(length=128), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("runtime_ms", sa.Float(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["campaign_id"], ["research_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["campaign_experiment_id"], ["campaign_experiments.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint("campaign_id", "idempotency_key", name="uq_campaign_jobs_idempotency"),
    )
    op.create_index("ix_campaign_jobs_status_created", "campaign_jobs", ["status", "created_at"])
    op.create_table(
        "strategy_rankings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_experiment_id", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("component_scores", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ranking_reason", sa.Text(), nullable=False),
        sa.Column("risk_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["campaign_id"], ["research_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["campaign_experiment_id"], ["campaign_experiments.id"], ondelete="CASCADE"
        ),
    )
    op.create_table(
        "portfolio_evaluations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column(
            "strategy_experiment_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("weighting_method", sa.String(length=64), nullable=False),
        sa.Column("weights", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("diversification_benefit", sa.Float(), nullable=False),
        sa.Column("correlation_matrix", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["campaign_id"], ["research_campaigns.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("portfolio_evaluations")
    op.drop_table("strategy_rankings")
    op.drop_index("ix_campaign_jobs_status_created", table_name="campaign_jobs")
    op.drop_table("campaign_jobs")
    op.drop_table("campaign_experiments")
    op.drop_table("research_campaigns")
