"""add durable campaign research queue

Revision ID: 20260830_0023
Revises: 20260830_0022
"""

import sqlalchemy as sa

from alembic import op

revision = "20260830_0023"
down_revision = "20260830_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "research_campaigns",
        sa.Column("research_queue", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("research_campaigns", "research_queue")
