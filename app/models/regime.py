import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MarketRegimeLabel(Base):
    __tablename__ = "market_regime_labels"
    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "interval",
            "timestamp",
            "regime_version",
            name="uq_market_regime_symbol_interval_ts_version",
        ),
        Index(
            "ix_market_regime_symbol_interval_ts",
            "symbol",
            "interval",
            "timestamp",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    interval: Mapped[str] = mapped_column(String(16), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    features: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    trend_regime: Mapped[str] = mapped_column(String(32), nullable=False)
    volatility_regime: Mapped[str] = mapped_column(String(32), nullable=False)
    character_regime: Mapped[str] = mapped_column(String(32), nullable=False)
    composite_regime: Mapped[str] = mapped_column(String(96), nullable=False)
    regime_version: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
