"""Add replayable walk-forward production simulations and temporal memory metadata."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260827_0018"
down_revision: str | None = "20260827_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("research_memory_lessons", sa.Column("available_from", sa.Date(), nullable=True))
    op.execute(
        "UPDATE research_memory_lessons "
        "SET available_from = CAST(period_end AS DATE) "
        "WHERE available_from IS NULL"
    )
    op.alter_column("research_memory_lessons", "available_from", nullable=False)
    op.create_table(
        "production_simulations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("universe", sa.JSON(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("research_window_days", sa.Integer(), nullable=False),
        sa.Column("deployment_window_days", sa.Integer(), nullable=False),
        sa.Column("cadence_days", sa.Integer(), nullable=False),
        sa.Column("initial_capital", sa.Numeric(18, 6), nullable=False),
        sa.Column("execution_model", sa.JSON(), nullable=False),
        sa.Column("data_versions", sa.JSON(), nullable=False),
        sa.Column("strategy_versions", sa.JSON(), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("timeline", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("production_simulations")
    op.drop_column("research_memory_lessons", "available_from")
