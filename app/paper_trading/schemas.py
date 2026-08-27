from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.paper_trading.events import ExecutionMode


class PaperTradingSessionCreateRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    start: date
    end: date
    interval: str = "1d"
    strategy_name: str = "moving_average_crossover"
    strategy_parameters: dict[str, int] = Field(
        default_factory=lambda: {"fast_window": 20, "slow_window": 50}
    )
    execution_mode: ExecutionMode = ExecutionMode.PAPER
    initial_cash: float = Field(default=10_000.0, gt=0)
    commission_bps: float = Field(default=1.0, ge=0)
    slippage_bps: float = Field(default=0.0, ge=0)
    target_exposure_pct: float = Field(default=0.95, gt=0, le=1.0)
    max_position_quantity: float = Field(default=1_000_000.0, gt=0)
    max_order_value: float = Field(default=1_000_000.0, gt=0)
    max_gross_exposure_pct: float = Field(default=1.0, gt=0)

    @model_validator(mode="after")
    def validate_request(self) -> "PaperTradingSessionCreateRequest":
        if self.start >= self.end:
            raise ValueError("start must be before end")
        if self.execution_mode != ExecutionMode.PAPER:
            raise ValueError("only PAPER execution mode is supported")
        return self


class LivePaperTradingSessionCreateRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    interval: str = "1m"
    strategy_name: str = "moving_average_crossover"
    strategy_parameters: dict[str, int] = Field(
        default_factory=lambda: {"fast_window": 20, "slow_window": 50}
    )
    execution_mode: ExecutionMode = ExecutionMode.PAPER
    initial_cash: float = Field(default=10_000.0, gt=0)
    commission_bps: float = Field(default=1.0, ge=0)
    slippage_bps: float = Field(default=0.0, ge=0)
    target_exposure_pct: float = Field(default=0.95, gt=0, le=1.0)
    max_position_quantity: float = Field(default=1_000_000.0, gt=0)
    max_order_value: float = Field(default=1_000_000.0, gt=0)
    max_gross_exposure_pct: float = Field(default=1.0, gt=0)
    warmup_start: date | None = None
    warmup_end: date | None = None
    respect_market_hours: bool = False
    max_events: int | None = Field(default=None, gt=0)
    max_reconnect_attempts: int = Field(default=3, ge=0)
    reconnect_backoff_seconds: float = Field(default=1.0, ge=0)

    @model_validator(mode="after")
    def validate_live_request(self) -> "LivePaperTradingSessionCreateRequest":
        if self.execution_mode != ExecutionMode.PAPER:
            raise ValueError("only PAPER execution mode is supported")
        if (self.warmup_start is None) != (self.warmup_end is None):
            raise ValueError("warmup_start and warmup_end must be supplied together")
        if (
            self.warmup_start is not None
            and self.warmup_end is not None
            and self.warmup_start >= self.warmup_end
        ):
            raise ValueError("warmup_start must be before warmup_end")
        return self


class PaperTradingSessionResponse(BaseModel):
    id: UUID
    strategy_name: str
    strategy_parameters: dict[str, Any]
    symbol: str
    interval: str
    start_date: date
    end_date: date
    execution_mode: str
    status: str
    initial_cash: Decimal
    commission_bps: float
    slippage_bps: float
    risk_config: dict[str, Any]
    metrics: dict[str, Any]
    final_portfolio: dict[str, Any]
    error_message: str | None
    started_at: datetime
    ended_at: datetime | None

    model_config = {"from_attributes": True}


class ComponentHealthResponse(BaseModel):
    component: str
    status: str
    reason: str | None = None


class PaperOrderResponse(BaseModel):
    id: UUID
    session_id: UUID
    strategy_id: str
    symbol: str
    side: str
    quantity: Decimal
    status: str
    created_at: datetime
    rejection_reason: str | None

    model_config = {"from_attributes": True}


class PaperFillResponse(BaseModel):
    id: UUID
    session_id: UUID
    order_id: UUID
    strategy_id: str
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    gross_notional: Decimal
    fees: Decimal
    slippage_cost: Decimal
    timestamp: datetime

    model_config = {"from_attributes": True}
