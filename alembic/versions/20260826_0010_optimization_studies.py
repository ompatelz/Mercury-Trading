"""Persist optimization studies and their campaign-backed trials.

Revision ID: 20260826_0010
Revises: 20260826_0009
"""

import sqlalchemy as sa

from alembic import op

revision = "20260826_0010"
down_revision = "20260826_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "optimization_studies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("campaign_id", sa.Uuid(), nullable=False),
        sa.Column("strategy_family", sa.String(length=100), nullable=False),
        sa.Column("parameter_space", sa.JSON(), nullable=False),
        sa.Column("objective_definition", sa.JSON(), nullable=False),
        sa.Column("dataset", sa.JSON(), nullable=False),
        sa.Column("validation_configuration", sa.JSON(), nullable=False),
        sa.Column("trial_budget", sa.Integer(), nullable=False),
        sa.Column("search_method", sa.String(length=32), nullable=False),
        sa.Column("random_seed", sa.Integer(), nullable=False),
        sa.Column("optimizer_metadata", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["campaign_id"], ["research_campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id"),
    )
    op.create_table(
        "optimization_trials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("study_id", sa.Uuid(), nullable=False),
        sa.Column("campaign_experiment_id", sa.Uuid(), nullable=False),
        sa.Column("experiment_id", sa.Uuid(), nullable=True),
        sa.Column("trial_number", sa.Integer(), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("parameter_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("rejection_reasons", sa.JSON(), nullable=False),
        sa.Column("objective_components", sa.JSON(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("sensitivity", sa.JSON(), nullable=False),
        sa.Column("engine", sa.String(length=64), nullable=True),
        sa.Column("engine_version", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["study_id"], ["optimization_studies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["campaign_experiment_id"], ["campaign_experiments.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["experiment_id"], ["experiments.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("study_id", "parameter_hash", name="uq_optimization_trials_parameters"),
        sa.UniqueConstraint("campaign_experiment_id"),
    )


def downgrade() -> None:
    op.drop_table("optimization_trials")
    op.drop_table("optimization_studies")
