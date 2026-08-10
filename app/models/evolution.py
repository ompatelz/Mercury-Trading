import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class EvolutionRun(Base):
    __tablename__ = "evolution_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    interval: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    memory_enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    memory_provenance: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    report: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    candidates: Mapped[list["StrategyCandidate"]] = relationship(
        back_populates="evolution_run", cascade="all, delete-orphan"
    )


class StrategyCandidate(Base):
    __tablename__ = "strategy_candidates"
    __table_args__ = (
        Index("ix_strategy_candidates_run_generation", "evolution_run_id", "generation"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    evolution_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("evolution_runs.id", ondelete="CASCADE"), nullable=False
    )
    parent_strategy_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    generation: Mapped[int] = mapped_column(nullable=False)
    strategy_specification: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    mutation_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    changed_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    fitness: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    regime_performance: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    diversity: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    promotion_status: Mapped[str] = mapped_column(String(32), nullable=False)
    memory_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    evolution_run: Mapped[EvolutionRun] = relationship(back_populates="candidates")
