import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Date, DateTime, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProductionSimulation(Base):
    """Replayable, paper-only walk-forward production simulation."""

    __tablename__ = "production_simulations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    universe: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    research_window_days: Mapped[int] = mapped_column(nullable=False)
    deployment_window_days: Mapped[int] = mapped_column(nullable=False)
    cadence_days: Mapped[int] = mapped_column(nullable=False)
    initial_capital: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    execution_model: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    data_versions: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    strategy_versions: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    timeline: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
