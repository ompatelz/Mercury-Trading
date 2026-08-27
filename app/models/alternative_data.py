import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ResearchAsset(Base):
    __tablename__ = "research_assets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    stable_identifier: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(32), nullable=False)
    exchange: Mapped[str | None] = mapped_column(String(64))
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_identifiers: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)


class ResearchUniverse(Base):
    __tablename__ = "research_universes"
    __table_args__ = (UniqueConstraint("name", "version", name="uq_research_universe_version"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    survivorship_bias_risk: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)


class ResearchUniverseMembership(Base):
    __tablename__ = "research_universe_memberships"
    __table_args__ = (
        UniqueConstraint("universe_id", "asset_id", name="uq_research_universe_member"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    universe_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_universes.id", ondelete="CASCADE"), nullable=False
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_assets.id", ondelete="RESTRICT"), nullable=False
    )
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
