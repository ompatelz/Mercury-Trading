"""add deterministic strategy health and research scheduling

Revision ID: 20260827_0018
Revises: 20260827_0017
"""

import sqlalchemy as sa

from alembic import op

revision = "20260827_0018"
down_revision = "20260827_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "strategy_health",
        sa.Column(
            "strategy_id",
            sa.Uuid(),
            sa.ForeignKey("strategy_candidates.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("lifecycle_state", sa.String(length=32), nullable=False),
        sa.Column("latest_score", sa.Float(), nullable=False),
        sa.Column("latest_components", sa.JSON(), nullable=False),
        sa.Column("active_flags", sa.JSON(), nullable=False),
        sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "strategy_health_observations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "strategy_id",
            sa.Uuid(),
            sa.ForeignKey("strategy_candidates.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("expected_metrics", sa.JSON(), nullable=False),
        sa.Column("components", sa.JSON(), nullable=False),
        sa.Column("flags", sa.JSON(), nullable=False),
        sa.Column("regime_context", sa.JSON(), nullable=False),
        sa.Column("execution_context", sa.JSON(), nullable=False),
        sa.Column("rule_version", sa.String(length=32), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_strategy_health_observations_strategy_time",
        "strategy_health_observations",
        ["strategy_id", "observed_at"],
    )
    op.create_table(
        "research_schedules",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "strategy_id", sa.Uuid(), sa.ForeignKey("strategy_candidates.id", ondelete="RESTRICT")
        ),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("cadence_days", sa.Integer()),
        sa.Column("campaign_template", sa.JSON(), nullable=False),
        sa.Column("trigger_types", sa.JSON(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "research_triggers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "strategy_id", sa.Uuid(), sa.ForeignKey("strategy_candidates.id", ondelete="RESTRICT")
        ),
        sa.Column("trigger_type", sa.String(length=64), nullable=False),
        sa.Column("deduplication_key", sa.String(length=128), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column(
            "campaign_id", sa.Uuid(), sa.ForeignKey("research_campaigns.id", ondelete="RESTRICT")
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("deduplication_key", name="uq_research_trigger_deduplication"),
    )
    op.create_index(
        "ix_research_triggers_strategy_created", "research_triggers", ["strategy_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_research_triggers_strategy_created", table_name="research_triggers")
    op.drop_table("research_triggers")
    op.drop_table("research_schedules")
    op.drop_index(
        "ix_strategy_health_observations_strategy_time", table_name="strategy_health_observations"
    )
    op.drop_table("strategy_health_observations")
    op.drop_table("strategy_health")
