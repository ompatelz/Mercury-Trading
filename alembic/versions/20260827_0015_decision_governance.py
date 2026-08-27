"""add immutable research decision governance

Revision ID: 20260827_0015
Revises: 20260827_0014
"""

import sqlalchemy as sa

from alembic import op

revision = "20260827_0015"
down_revision = "20260827_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "decision_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("decision_type", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("actor", sa.String(length=128), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("campaign_id", sa.Uuid()),
        sa.Column("experiment_id", sa.Uuid()),
        sa.Column("strategy_id", sa.Uuid()),
        sa.Column("workflow_experiment_id", sa.Uuid()),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("inputs", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("alternatives", sa.JSON(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("versions", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "supersedes_id",
            sa.Uuid(),
            sa.ForeignKey("decision_records.id", ondelete="RESTRICT"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_decisions_campaign_created", "decision_records", ["campaign_id", "created_at"]
    )
    op.create_index(
        "ix_decisions_strategy_created", "decision_records", ["strategy_id", "created_at"]
    )
    op.create_index(
        "ix_decisions_type_created", "decision_records", ["decision_type", "created_at"]
    )
    op.create_table(
        "decision_rule_evaluations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "decision_id",
            sa.Uuid(),
            sa.ForeignKey("decision_records.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rule", sa.String(length=128), nullable=False),
        sa.Column("rule_version", sa.String(length=32), nullable=False),
        sa.Column("threshold", sa.JSON(), nullable=True),
        sa.Column("observed_value", sa.JSON(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("detail", sa.Text()),
    )


def downgrade() -> None:
    op.drop_table("decision_rule_evaluations")
    op.drop_index("ix_decisions_type_created", table_name="decision_records")
    op.drop_index("ix_decisions_strategy_created", table_name="decision_records")
    op.drop_index("ix_decisions_campaign_created", table_name="decision_records")
    op.drop_table("decision_records")
