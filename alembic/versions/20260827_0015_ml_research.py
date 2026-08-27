"""add deterministic ML research registry and prediction lineage

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
        "ml_models",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("model_key", sa.String(128), unique=True, nullable=False),
        sa.Column("algorithm", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column(
            "dataset_version_id",
            sa.Uuid(),
            sa.ForeignKey("dataset_versions.id", ondelete="RESTRICT"),
        ),
        sa.Column("dataset_fingerprint", sa.String(64), nullable=False),
        sa.Column("feature_versions", sa.JSON(), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("artifact_location", sa.Text(), nullable=False),
        sa.Column("artifact_checksum", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_table(
        "ml_predictions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "model_id",
            sa.Uuid(),
            sa.ForeignKey("ml_models.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("asset_id", sa.String(64), nullable=False),
        sa.Column("prediction", sa.Float(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float()),
        sa.Column("feature_fingerprint", sa.String(64), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ml_predictions")
    op.drop_table("ml_models")
