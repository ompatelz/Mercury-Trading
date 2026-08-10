"""Add paper-trading execution tables.

Revision ID: 20260810_0007
Revises: 20260810_0006
Create Date: 2026-08-10 15:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260810_0007"
down_revision: str | None = "20260810_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "paper_trading_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("strategy_name", sa.String(length=100), nullable=False),
        sa.Column("strategy_parameters", sa.JSON(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("interval", sa.String(length=16), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("execution_mode", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("initial_cash", sa.Numeric(18, 6), nullable=False),
        sa.Column("commission_bps", sa.Float(), nullable=False),
        sa.Column("slippage_bps", sa.Float(), nullable=False),
        sa.Column("risk_config", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("final_portfolio", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "paper_orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("strategy_id", sa.String(length=100), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 10), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["paper_trading_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_paper_orders_session_created", "paper_orders", ["session_id", "created_at"])
    op.create_index("ix_paper_orders_session_status", "paper_orders", ["session_id", "status"])
    op.create_table(
        "paper_fills",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("strategy_id", sa.String(length=100), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 10), nullable=False),
        sa.Column("price", sa.Numeric(18, 6), nullable=False),
        sa.Column("gross_notional", sa.Numeric(18, 6), nullable=False),
        sa.Column("fees", sa.Numeric(18, 6), nullable=False),
        sa.Column("slippage_cost", sa.Numeric(18, 6), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["paper_orders.id"]),
        sa.ForeignKeyConstraint(["session_id"], ["paper_trading_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_paper_fills_session_timestamp", "paper_fills", ["session_id", "timestamp"])
    op.create_table(
        "paper_trace_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["paper_trading_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_paper_events_session_sequence", "paper_trace_events", ["session_id", "sequence"]
    )


def downgrade() -> None:
    op.drop_index("ix_paper_events_session_sequence", table_name="paper_trace_events")
    op.drop_table("paper_trace_events")
    op.drop_index("ix_paper_fills_session_timestamp", table_name="paper_fills")
    op.drop_table("paper_fills")
    op.drop_index("ix_paper_orders_session_status", table_name="paper_orders")
    op.drop_index("ix_paper_orders_session_created", table_name="paper_orders")
    op.drop_table("paper_orders")
    op.drop_table("paper_trading_sessions")
