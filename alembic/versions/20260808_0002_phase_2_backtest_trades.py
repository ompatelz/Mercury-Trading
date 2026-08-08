"""Add Phase 2 backtest trade records.

Revision ID: 20260808_0002
Revises: 20260808_0001
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260808_0002"
down_revision: str | None = "20260808_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "experiments",
        sa.Column("slippage_bps", sa.Float(), server_default="0", nullable=False),
    )
    op.add_column(
        "experiments",
        sa.Column(
            "run_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.create_table(
        "backtest_trades",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("experiment_id", sa.Uuid(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 10), nullable=False),
        sa.Column("price", sa.Numeric(18, 6), nullable=False),
        sa.Column("notional", sa.Numeric(18, 6), nullable=False),
        sa.Column("transaction_cost", sa.Numeric(18, 6), nullable=False),
        sa.Column("slippage_cost", sa.Numeric(18, 6), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(18, 6), nullable=True),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_backtest_trades_experiment_timestamp",
        "backtest_trades",
        ["experiment_id", "timestamp"],
    )


def downgrade() -> None:
    op.drop_index("ix_backtest_trades_experiment_timestamp", table_name="backtest_trades")
    op.drop_table("backtest_trades")
    op.drop_column("experiments", "run_metadata")
    op.drop_column("experiments", "slippage_bps")
