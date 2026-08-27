import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PaperTradingSession(Base):
    __tablename__ = "paper_trading_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    strategy_name: Mapped[str] = mapped_column(String(100), nullable=False)
    strategy_parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    interval: Mapped[str] = mapped_column(String(16), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    initial_cash: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    commission_bps: Mapped[float] = mapped_column(nullable=False)
    slippage_bps: Mapped[float] = mapped_column(nullable=False)
    risk_config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    final_portfolio: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    orders: Mapped[list["PaperOrderRecord"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    fills: Mapped[list["PaperFillRecord"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    events: Mapped[list["PaperTraceEventRecord"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class PaperOrderRecord(Base):
    __tablename__ = "paper_orders"
    __table_args__ = (
        Index("ix_paper_orders_session_created", "session_id", "created_at"),
        Index("ix_paper_orders_session_status", "session_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("paper_trading_sessions.id", ondelete="CASCADE"), nullable=False
    )
    strategy_id: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    session: Mapped[PaperTradingSession] = relationship(back_populates="orders")


class PaperFillRecord(Base):
    __tablename__ = "paper_fills"
    __table_args__ = (Index("ix_paper_fills_session_timestamp", "session_id", "timestamp"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("paper_trading_sessions.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("paper_orders.id"), nullable=False)
    strategy_id: Mapped[str] = mapped_column(String(100), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(24, 10), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    gross_notional: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    fees: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    slippage_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    session: Mapped[PaperTradingSession] = relationship(back_populates="fills")


class PaperTraceEventRecord(Base):
    __tablename__ = "paper_trace_events"
    __table_args__ = (Index("ix_paper_events_session_sequence", "session_id", "sequence"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("paper_trading_sessions.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    session: Mapped[PaperTradingSession] = relationship(back_populates="events")
