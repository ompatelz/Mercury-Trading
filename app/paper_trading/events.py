from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class EventType(StrEnum):
    MARKET = "MARKET"
    SIGNAL = "SIGNAL"
    ORDER = "ORDER"
    FILL = "FILL"
    PORTFOLIO = "PORTFOLIO"
    SESSION = "SESSION"
    ERROR = "ERROR"


class SignalDirection(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    EXIT = "EXIT"
    HOLD = "HOLD"


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(StrEnum):
    CREATED = "CREATED"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class ExecutionMode(StrEnum):
    PAPER = "PAPER"


@dataclass(frozen=True)
class MarketEvent:
    session_id: UUID
    timestamp: datetime
    symbol: str
    interval: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    sequence: int
    bid: float | None = None
    ask: float | None = None
    last_price: float | None = None

    @property
    def event_type(self) -> EventType:
        return EventType.MARKET


@dataclass(frozen=True)
class SignalEvent:
    session_id: UUID
    signal_id: UUID
    strategy_id: str
    symbol: str
    timestamp: datetime
    direction: SignalDirection
    strength: float
    intended_quantity: float
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def event_type(self) -> EventType:
        return EventType.SIGNAL


@dataclass(frozen=True)
class OrderEvent:
    session_id: UUID
    order_id: UUID
    strategy_id: str
    symbol: str
    side: OrderSide
    quantity: float
    created_at: datetime
    status: OrderStatus
    reason: str | None = None
    filled_quantity: float = 0.0
    average_fill_price: float = 0.0
    order_type: str = "MARKET"
    limit_price: float | None = None

    @property
    def event_type(self) -> EventType:
        return EventType.ORDER


@dataclass(frozen=True)
class FillEvent:
    session_id: UUID
    fill_id: UUID
    order_id: UUID
    strategy_id: str
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    gross_notional: float
    fees: float
    slippage_cost: float
    timestamp: datetime
    spread_cost: float = 0.0
    impact_cost: float = 0.0

    @property
    def event_type(self) -> EventType:
        return EventType.FILL


@dataclass(frozen=True)
class PortfolioEvent:
    session_id: UUID
    timestamp: datetime
    cash: float
    positions: dict[str, dict[str, float]]
    realized_pnl: float
    unrealized_pnl: float
    equity: float
    exposure: float
    transaction_costs: float

    @property
    def event_type(self) -> EventType:
        return EventType.PORTFOLIO


def new_id() -> UUID:
    return uuid4()
