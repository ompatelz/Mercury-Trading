import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StrategyHealth(Base):
    __tablename__ = "strategy_health"

    strategy_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("strategy_candidates.id", ondelete="RESTRICT"), primary_key=True
    )
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    lifecycle_state: Mapped[str] = mapped_column(String(32), nullable=False)
    latest_score: Mapped[float] = mapped_column(nullable=False)
    latest_components: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    active_flags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    last_evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class StrategyHealthObservation(Base):
    __tablename__ = "strategy_health_observations"
    __table_args__ = (
        Index("ix_strategy_health_observations_strategy_time", "strategy_id", "observed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    strategy_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("strategy_candidates.id", ondelete="RESTRICT"), nullable=False
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    expected_metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    components: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    flags: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    regime_context: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    execution_context: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    rule_version: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ResearchSchedule(Base):
    __tablename__ = "research_schedules"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("strategy_candidates.id", ondelete="RESTRICT"), nullable=True
    )
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    cadence_days: Mapped[int | None] = mapped_column(nullable=True)
    campaign_template: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    trigger_types: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ResearchTrigger(Base):
    __tablename__ = "research_triggers"
    __table_args__ = (
        UniqueConstraint("deduplication_key", name="uq_research_trigger_deduplication"),
        Index("ix_research_triggers_strategy_created", "strategy_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("strategy_candidates.id", ondelete="RESTRICT"), nullable=True
    )
    trigger_type: Mapped[str] = mapped_column(String(64), nullable=False)
    deduplication_key: Mapped[str] = mapped_column(String(128), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("research_campaigns.id", ondelete="RESTRICT"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
