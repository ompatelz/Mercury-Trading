"""Persist reproducible portfolio definitions and evaluation evidence.

Revision ID: 20260826_0011
Revises: 20260826_0010
"""

import sqlalchemy as sa

from alembic import op

revision = "20260826_0011"
down_revision = "20260826_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name, type_, default in [
        ("definition", sa.JSON(), "{}"),
        ("compatibility", sa.JSON(), "{}"),
        ("rebalance_history", sa.JSON(), "[]"),
        ("incremental_benefit", sa.JSON(), "{}"),
        ("rejection_reasons", sa.JSON(), "[]"),
        ("ranking", sa.JSON(), "{}"),
    ]:
        op.add_column(
            "portfolio_evaluations",
            sa.Column(name, type_, nullable=False, server_default=sa.text(f"'{default}'")),
        )


def downgrade() -> None:
    for name in [
        "ranking",
        "rejection_reasons",
        "incremental_benefit",
        "rebalance_history",
        "compatibility",
        "definition",
    ]:
        op.drop_column("portfolio_evaluations", name)
