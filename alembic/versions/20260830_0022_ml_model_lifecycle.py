# ruff: noqa: E501
"""add ML lifecycle, drift, and promotion evidence

Revision ID: 20260830_0022
Revises: 20260827_0021
"""

import sqlalchemy as sa

from alembic import op

revision = "20260830_0022"
down_revision = "20260827_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ml_models", sa.Column("parent_model_id", sa.Uuid(), nullable=True))
    op.add_column(
        "ml_models", sa.Column("lifecycle_metadata", sa.JSON(), nullable=False, server_default="{}")
    )
    op.create_foreign_key(
        "fk_ml_models_parent_model_id",
        "ml_models",
        "ml_models",
        ["parent_model_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_table(
        "ml_drift_observations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "model_id", sa.Uuid(), sa.ForeignKey("ml_models.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("baseline", sa.JSON(), nullable=False),
        sa.Column("observed", sa.JSON(), nullable=False),
        sa.Column("drift_types", sa.JSON(), nullable=False),
        sa.Column("consecutive_windows", sa.Integer(), nullable=False),
        sa.Column("retraining_triggered", sa.Boolean(), nullable=False),
        sa.Column("rule_version", sa.String(32), nullable=False),
    )
    op.create_table(
        "ml_model_promotions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "candidate_model_id",
            sa.Uuid(),
            sa.ForeignKey("ml_models.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "champion_model_id", sa.Uuid(), sa.ForeignKey("ml_models.id", ondelete="RESTRICT")
        ),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_table("ml_model_promotions")
    op.drop_table("ml_drift_observations")
    op.drop_constraint("fk_ml_models_parent_model_id", "ml_models", type_="foreignkey")
    op.drop_column("ml_models", "lifecycle_metadata")
    op.drop_column("ml_models", "parent_model_id")
