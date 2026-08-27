"""add model routing usage tracking

Revision ID: 20260827_0013
Revises: 20260826_0012
"""

import sqlalchemy as sa

from alembic import op

revision = "20260827_0013"
down_revision = "20260826_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_usage_calls",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("agent", sa.String(length=100), nullable=False),
        sa.Column("model_id", sa.String(length=160), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("estimated_cost", sa.Float(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("fallback_used", sa.Boolean(), nullable=False),
        sa.Column("escalation_reason", sa.Text(), nullable=True),
        sa.Column("routing_decision", sa.JSON(), nullable=False),
        sa.Column(
            "research_experiment_id",
            sa.Uuid(),
            sa.ForeignKey("research_experiments.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "campaign_id", sa.Uuid(), sa.ForeignKey("research_campaigns.id", ondelete="SET NULL")
        ),
        sa.Column(
            "workflow_version_id",
            sa.Uuid(),
            sa.ForeignKey("workflow_versions.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("model_usage_calls")
