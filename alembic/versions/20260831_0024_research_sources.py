"""add immutable text research-source attachments

Revision ID: 20260831_0024
Revises: 20260830_0023
"""

import sqlalchemy as sa

from alembic import op

revision = "20260831_0024"
down_revision = "20260830_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_sources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("sha256", sa.String(length=64), nullable=False, unique=True),
        sa.Column("content_type", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "research_source_attachments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "research_experiment_id",
            sa.Uuid(),
            sa.ForeignKey("research_experiments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "research_source_id",
            sa.Uuid(),
            sa.ForeignKey("research_sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("original_filename", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "research_experiment_id", "research_source_id", name="uq_research_source_attachment"
        ),
    )
    op.create_index(
        "ix_research_source_attachments_experiment",
        "research_source_attachments",
        ["research_experiment_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_research_source_attachments_experiment", table_name="research_source_attachments"
    )
    op.drop_table("research_source_attachments")
    op.drop_table("research_sources")
