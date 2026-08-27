import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ResearchMemoryLesson(Base):
    __tablename__ = "research_memory_lessons"
    __table_args__ = (
        Index("ix_memory_strategy_regime", "strategy_family", "market_regime"),
        Index("ix_memory_symbol_failure", "symbol", "failure_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    research_experiment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_experiments.id", ondelete="CASCADE"), nullable=False
    )
    backtest_experiment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("experiments.id", ondelete="SET NULL"), nullable=True
    )
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    strategy_family: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(32), nullable=False)
    market_regime: Mapped[str] = mapped_column(String(100), nullable=False)
    period_start: Mapped[str] = mapped_column(String(16), nullable=False)
    period_end: Mapped[str] = mapped_column(String(16), nullable=False)
    available_from: Mapped[date] = mapped_column(Date, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    risk_flags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    failure_reasons: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    critic_summary: Mapped[str] = mapped_column(Text, nullable=False)
    observations: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(JSON, default=list, nullable=False)
    agent_version: Mapped[str] = mapped_column(String(64), nullable=False)
    workflow_version: Mapped[str] = mapped_column(String(64), nullable=False)
    failure_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
