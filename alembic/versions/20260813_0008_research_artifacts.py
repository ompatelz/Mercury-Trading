"""Add reproducible research artifacts.

Revision ID: 20260813_0008
Revises: 20260810_0007
Create Date: 2026-08-13 13:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260813_0008"
down_revision: str | None = "20260810_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("artifact_type", sa.String(length=32), nullable=False),
        sa.Column("experiment_id", sa.Uuid(), nullable=True),
        sa.Column("campaign_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("hypothesis", sa.Text(), nullable=True),
        sa.Column("methodology", sa.JSON(), nullable=False),
        sa.Column("strategy_definition", sa.JSON(), nullable=False),
        sa.Column("dataset", sa.JSON(), nullable=False),
        sa.Column("validation_method", sa.JSON(), nullable=False),
        sa.Column("performance_metrics", sa.JSON(), nullable=False),
        sa.Column("risk_metrics", sa.JSON(), nullable=False),
        sa.Column("regime_metrics", sa.JSON(), nullable=False),
        sa.Column("risk_flags", sa.JSON(), nullable=False),
        sa.Column("overfitting_flags", sa.JSON(), nullable=False),
        sa.Column("critic_summary", sa.JSON(), nullable=False),
        sa.Column("conclusion", sa.JSON(), nullable=False),
        sa.Column("measured_results", sa.JSON(), nullable=False),
        sa.Column("interpretation", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("reproducibility_metadata", sa.JSON(), nullable=False),
        sa.Column("charts", sa.JSON(), nullable=False),
        sa.Column("export_metadata", sa.JSON(), nullable=False),
        sa.Column("markdown_report", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["campaign_id"], ["research_campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("artifact_type", "campaign_id", name="uq_artifact_campaign_type"),
        sa.UniqueConstraint("artifact_type", "experiment_id", name="uq_artifact_experiment_type"),
    )


def downgrade() -> None:
    op.drop_table("research_artifacts")
