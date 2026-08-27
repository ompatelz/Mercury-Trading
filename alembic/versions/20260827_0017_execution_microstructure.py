"""Persist paper-order fill progress for deterministic microstructure execution.

Revision ID: 20260827_0017
Revises: 20260827_0016
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260827_0017"
down_revision: str | None = "20260827_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "paper_orders",
        sa.Column("filled_quantity", sa.Numeric(24, 10), nullable=False, server_default="0"),
    )
    op.add_column(
        "paper_orders",
        sa.Column("average_fill_price", sa.Numeric(18, 6), nullable=False, server_default="0"),
    )
    op.alter_column("paper_orders", "filled_quantity", server_default=None)
    op.alter_column("paper_orders", "average_fill_price", server_default=None)


def downgrade() -> None:
    op.drop_column("paper_orders", "average_fill_price")
    op.drop_column("paper_orders", "filled_quantity")
