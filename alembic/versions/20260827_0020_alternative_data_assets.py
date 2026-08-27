"""add stable research assets and versioned universes

Revision ID: 20260827_0020
Revises: 20260827_0019
"""

import sqlalchemy as sa

from alembic import op

revision = "20260827_0020"
down_revision = "20260827_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_assets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("stable_identifier", sa.String(128), nullable=False, unique=True),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("asset_class", sa.String(32), nullable=False),
        sa.Column("exchange", sa.String(64)),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("provider_identifiers", sa.JSON(), nullable=False),
    )
    op.create_table(
        "research_universes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True)),
        sa.Column("survivorship_bias_risk", sa.Boolean(), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.UniqueConstraint("name", "version", name="uq_research_universe_version"),
    )
    op.create_table(
        "research_universe_memberships",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "universe_id",
            sa.Uuid(),
            sa.ForeignKey("research_universes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "asset_id",
            sa.Uuid(),
            sa.ForeignKey("research_assets.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("universe_id", "asset_id", name="uq_research_universe_member"),
    )


def downgrade() -> None:
    op.drop_table("research_universe_memberships")
    op.drop_table("research_universes")
    op.drop_table("research_assets")
