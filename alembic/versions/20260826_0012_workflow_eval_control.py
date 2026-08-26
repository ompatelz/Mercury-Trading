"""add controlled workflow evaluation records

Revision ID: 20260826_0012
Revises: 20260826_0011
"""

import sqlalchemy as sa

from alembic import op

revision = "20260826_0012"
down_revision = "20260826_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workflow_versions",
        sa.Column("manifest", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column(
        "eval_runs",
        sa.Column("benchmark_version", sa.String(length=32), nullable=False, server_default="v1"),
    )
    op.add_column(
        "eval_runs",
        sa.Column("execution_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column(
        "eval_task_results",
        sa.Column("output", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column(
        "eval_task_results",
        sa.Column("token_usage", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.add_column(
        "eval_task_results",
        sa.Column("estimated_cost", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "eval_task_results", sa.Column("failure_type", sa.String(length=100), nullable=True)
    )
    op.create_table(
        "workflow_experiments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "baseline_workflow_version_id",
            sa.Uuid(),
            sa.ForeignKey("workflow_versions.id"),
            nullable=False,
        ),
        sa.Column(
            "candidate_workflow_version_id",
            sa.Uuid(),
            sa.ForeignKey("workflow_versions.id"),
            nullable=False,
        ),
        sa.Column("benchmark_name", sa.String(length=100), nullable=False),
        sa.Column("benchmark_version", sa.String(length=32), nullable=False),
        sa.Column("baseline_eval_run_id", sa.Uuid(), sa.ForeignKey("eval_runs.id"), nullable=False),
        sa.Column(
            "candidate_eval_run_id", sa.Uuid(), sa.ForeignKey("eval_runs.id"), nullable=False
        ),
        sa.Column("promotion_config", sa.JSON(), nullable=False),
        sa.Column("comparison", sa.JSON(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "workflow_candidate_changes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "workflow_version_id", sa.Uuid(), sa.ForeignKey("workflow_versions.id"), nullable=False
        ),
        sa.Column("change_kind", sa.String(length=64), nullable=False),
        sa.Column("observed_failure", sa.Text(), nullable=False),
        sa.Column("changes", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "workflow_champions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("component", sa.String(length=100), nullable=False),
        sa.Column(
            "workflow_version_id", sa.Uuid(), sa.ForeignKey("workflow_versions.id"), nullable=False
        ),
        sa.Column("promoted_from_experiment_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("component", name="uq_workflow_champions_component"),
    )


def downgrade() -> None:
    op.drop_table("workflow_champions")
    op.drop_table("workflow_candidate_changes")
    op.drop_table("workflow_experiments")
    op.drop_column("eval_task_results", "failure_type")
    op.drop_column("eval_task_results", "estimated_cost")
    op.drop_column("eval_task_results", "token_usage")
    op.drop_column("eval_task_results", "output")
    op.drop_column("eval_runs", "execution_metadata")
    op.drop_column("eval_runs", "benchmark_version")
    op.drop_column("workflow_versions", "manifest")
