"""Add durable leasing and observability fields to campaign jobs.

Revision ID: 20260826_0009
Revises: 20260813_0008
"""

import sqlalchemy as sa

from alembic import op

revision = "20260826_0009"
down_revision = "20260813_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_campaign_jobs_status_created", table_name="campaign_jobs")
    op.add_column("campaign_jobs", sa.Column("experiment_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_campaign_jobs_experiment_id",
        "campaign_jobs",
        "experiments",
        ["experiment_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "campaign_jobs",
        sa.Column("payload_version", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "campaign_jobs", sa.Column("priority", sa.Integer(), server_default="0", nullable=False)
    )
    op.add_column(
        "campaign_jobs", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "campaign_jobs",
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )
    op.add_column(
        "campaign_jobs",
        sa.Column("cancel_requested", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "campaign_jobs",
        sa.Column("retry_history", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
    )
    op.add_column("campaign_jobs", sa.Column("error_type", sa.String(length=128), nullable=True))
    op.create_index(
        "ix_campaign_jobs_status_available_priority",
        "campaign_jobs",
        ["status", "available_at", "priority"],
    )


def downgrade() -> None:
    op.drop_index("ix_campaign_jobs_status_available_priority", table_name="campaign_jobs")
    op.drop_constraint("fk_campaign_jobs_experiment_id", "campaign_jobs", type_="foreignkey")
    for name in [
        "error_type",
        "retry_history",
        "cancel_requested",
        "available_at",
        "heartbeat_at",
        "priority",
        "payload_version",
        "experiment_id",
    ]:
        op.drop_column("campaign_jobs", name)
    op.create_index("ix_campaign_jobs_status_created", "campaign_jobs", ["status", "created_at"])
