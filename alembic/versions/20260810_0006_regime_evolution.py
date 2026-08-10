"""Add regime-aware strategy evolution tables.

Revision ID: 20260810_0006
Revises: 20260810_0005
Create Date: 2026-08-10 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260810_0006"
down_revision: str | None = "20260810_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "market_regime_labels",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("interval", sa.String(length=16), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("trend_regime", sa.String(length=32), nullable=False),
        sa.Column("volatility_regime", sa.String(length=32), nullable=False),
        sa.Column("character_regime", sa.String(length=32), nullable=False),
        sa.Column("composite_regime", sa.String(length=96), nullable=False),
        sa.Column("regime_version", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "symbol",
            "interval",
            "timestamp",
            "regime_version",
            name="uq_market_regime_symbol_interval_ts_version",
        ),
    )
    op.create_index(
        "ix_market_regime_symbol_interval_ts",
        "market_regime_labels",
        ["symbol", "interval", "timestamp"],
    )
    op.create_table(
        "evolution_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("interval", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("settings", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("memory_enabled", sa.Boolean(), nullable=False),
        sa.Column("memory_provenance", sa.JSON(), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "strategy_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("evolution_run_id", sa.Uuid(), nullable=False),
        sa.Column("parent_strategy_ids", sa.JSON(), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("strategy_specification", sa.JSON(), nullable=False),
        sa.Column("mutation_type", sa.String(length=64), nullable=True),
        sa.Column("changed_fields", sa.JSON(), nullable=False),
        sa.Column("fitness", sa.JSON(), nullable=False),
        sa.Column("regime_performance", sa.JSON(), nullable=False),
        sa.Column("diversity", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("promotion_status", sa.String(length=32), nullable=False),
        sa.Column("memory_ids", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["evolution_run_id"], ["evolution_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_strategy_candidates_run_generation",
        "strategy_candidates",
        ["evolution_run_id", "generation"],
    )


def downgrade() -> None:
    op.drop_index("ix_strategy_candidates_run_generation", table_name="strategy_candidates")
    op.drop_table("strategy_candidates")
    op.drop_table("evolution_runs")
    op.drop_index("ix_market_regime_symbol_interval_ts", table_name="market_regime_labels")
    op.drop_table("market_regime_labels")
