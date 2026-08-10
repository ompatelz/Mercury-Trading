from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class RegimeComputeRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    interval: str = "1d"
    start: date | None = None
    end: date | None = None
    lookback: int = Field(default=20, ge=3, le=252)
    regime_version: str = "regime-v1"


class RegimeLabelResponse(BaseModel):
    id: UUID
    symbol: str
    interval: str
    timestamp: datetime
    features: dict[str, Any]
    trend_regime: str
    volatility_regime: str
    character_regime: str
    composite_regime: str
    regime_version: str
    created_at: datetime

    model_config = {"from_attributes": True}
