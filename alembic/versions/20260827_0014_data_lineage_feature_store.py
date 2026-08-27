"""add immutable data lineage and feature store

Revision ID: 20260827_0014
Revises: 20260827_0013
"""

import sqlalchemy as sa

from alembic import op

revision = "20260827_0014"
down_revision = "20260827_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "datasets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "dataset_id",
            sa.Uuid(),
            sa.ForeignKey("datasets.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("symbols", sa.JSON(), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("frequency", sa.String(16), nullable=False),
        sa.Column("start_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "ingested_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("storage_location", sa.Text(), nullable=False),
        sa.Column("adjustment_policy", sa.String(64), nullable=False),
        sa.Column("quality_report", sa.JSON(), nullable=False),
        sa.UniqueConstraint("dataset_id", "version", name="uq_dataset_versions_dataset_version"),
    )
    op.create_table(
        "dataset_lineage",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "child_dataset_version_id",
            sa.Uuid(),
            sa.ForeignKey("dataset_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_dataset_version_id",
            sa.Uuid(),
            sa.ForeignKey("dataset_versions.id", ondelete="RESTRICT"),
        ),
        sa.Column("transformation", sa.String(100), nullable=False),
        sa.Column("transformation_version", sa.String(32), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "dataset_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("dataset_version_ids", sa.JSON(), nullable=False),
        sa.Column("universe", sa.JSON(), nullable=False),
        sa.Column("feature_set", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "feature_definitions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "feature_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "feature_definition_id",
            sa.Uuid(),
            sa.ForeignKey("feature_definitions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("input_schema", sa.JSON(), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("implementation", sa.String(128), nullable=False),
        sa.Column("lookback", sa.Integer(), nullable=False),
        sa.Column("code_metadata", sa.JSON(), nullable=False),
        sa.UniqueConstraint(
            "feature_definition_id", "version", name="uq_feature_versions_definition_version"
        ),
    )
    op.create_table(
        "feature_materializations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "dataset_version_id",
            sa.Uuid(),
            sa.ForeignKey("dataset_versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "feature_version_id",
            sa.Uuid(),
            sa.ForeignKey("feature_versions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("parameters_hash", sa.String(64), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("storage_location", sa.Text(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "dataset_version_id",
            "feature_version_id",
            "parameters_hash",
            name="uq_feature_materializations_cache_key",
        ),
    )
    op.add_column(
        "experiments",
        sa.Column(
            "dataset_version_id",
            sa.Uuid(),
            sa.ForeignKey("dataset_versions.id", ondelete="RESTRICT"),
        ),
    )
    op.add_column(
        "experiments",
        sa.Column("feature_versions", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )
    op.add_column("experiments", sa.Column("data_fingerprint", sa.String(64)))
    op.add_column(
        "research_campaigns",
        sa.Column(
            "dataset_snapshot_id",
            sa.Uuid(),
            sa.ForeignKey("dataset_snapshots.id", ondelete="RESTRICT"),
        ),
    )
    op.add_column(
        "research_campaigns",
        sa.Column("feature_set", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    )


def downgrade() -> None:
    op.drop_column("research_campaigns", "feature_set")
    op.drop_column("research_campaigns", "dataset_snapshot_id")
    op.drop_column("experiments", "data_fingerprint")
    op.drop_column("experiments", "feature_versions")
    op.drop_column("experiments", "dataset_version_id")
    op.drop_table("feature_materializations")
    op.drop_table("feature_versions")
    op.drop_table("feature_definitions")
    op.drop_table("dataset_snapshots")
    op.drop_table("dataset_lineage")
    op.drop_table("dataset_versions")
    op.drop_table("datasets")
