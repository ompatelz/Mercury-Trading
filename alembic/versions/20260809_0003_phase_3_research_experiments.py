"""Add Phase 3 research experiment records.

Revision ID: 20260809_0003
Revises: 20260808_0002
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260809_0003"
down_revision: str | None = "20260808_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_experiments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("interval", sa.String(length=16), nullable=False),
        sa.Column("execution_engine", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("hypothesis", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("strategy", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("backtest_experiment_id", sa.Uuid(), nullable=True),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evaluation", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("critique", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("report", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("model_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("workflow_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["backtest_experiment_id"], ["experiments.id"], ondelete="SET NULL"
        ),
    )


def downgrade() -> None:
    op.drop_table("research_experiments")
