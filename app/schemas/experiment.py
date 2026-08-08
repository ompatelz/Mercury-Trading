from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class BacktestRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    start: date
    end: date
    interval: str = "1d"
    short_window: int = Field(default=20, ge=2)
    long_window: int = Field(default=50, ge=3)
    initial_capital: float = Field(default=10_000.0, gt=0)
    transaction_cost_bps: float = Field(default=1.0, ge=0)

    @model_validator(mode="after")
    def validate_windows(self) -> "BacktestRequest":
        if self.short_window >= self.long_window:
            raise ValueError("short_window must be less than long_window")
        if self.start >= self.end:
            raise ValueError("start must be before end")
        return self


class ExperimentResponse(BaseModel):
    id: UUID
    strategy_name: str
    symbol: str
    parameters: dict[str, Any]
    start_date: date
    end_date: date
    data_interval: str
    transaction_cost_bps: float
    created_at: datetime
    status: str
    metrics: dict[str, Any]
    error_message: str | None

    model_config = {"from_attributes": True}
