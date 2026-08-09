import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    strategy_name: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    data_interval: Mapped[str] = mapped_column(String(16), nullable=False)
    transaction_cost_bps: Mapped[float] = mapped_column(nullable=False)
    slippage_bps: Mapped[float] = mapped_column(default=0.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    run_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    trades: Mapped[list["BacktestTradeRecord"]] = relationship(
        back_populates="experiment", cascade="all, delete-orphan"
    )


class BacktestTradeRecord(Base):
    __tablename__ = "backtest_trades"
    __table_args__ = (
        Index("ix_backtest_trades_experiment_timestamp", "experiment_id", "timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    notional: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    transaction_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    slippage_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)

    experiment: Mapped[Experiment] = relationship(back_populates="trades")


class ResearchExperiment(Base):
    __tablename__ = "research_experiments"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    interval: Mapped[str] = mapped_column(String(16), nullable=False)
    execution_engine: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    hypothesis: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    strategy: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    backtest_experiment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("experiments.id", ondelete="SET NULL"), nullable=True
    )
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    evaluation: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    critique: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    report: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    model_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    workflow_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
