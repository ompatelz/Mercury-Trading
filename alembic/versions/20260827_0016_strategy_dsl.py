"""add immutable validated strategy DSL records

Revision ID: 20260827_0016
Revises: 20260827_0015
"""

import sqlalchemy as sa

from alembic import op

revision = "20260827_0016"
down_revision = "20260827_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "strategy_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("strategy_hash", sa.String(length=64), unique=True, nullable=False),
        sa.Column("dsl_version", sa.String(length=32), nullable=False),
        sa.Column("compiler_version", sa.String(length=64), nullable=False),
        sa.Column("spec", sa.JSON(), nullable=False),
        sa.Column("validation", sa.JSON(), nullable=False),
        sa.Column("complexity", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("strategy_records")
