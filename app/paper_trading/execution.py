"""Deterministic, quote-based execution models for PAPER-only simulation.

This module deliberately models executable quotes and bar-volume liquidity, not a
full exchange order book.  Quotes derived from OHLC bars are labelled synthetic.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.paper_trading.events import (
    FillEvent,
    MarketEvent,
    OrderEvent,
    OrderSide,
    OrderStatus,
    new_id,
)


class ExecutionModelName(StrEnum):
    IDEAL = "IDEAL"
    BASIC_SLIPPAGE = "BASIC_SLIPPAGE"
    MICROSTRUCTURE = "MICROSTRUCTURE"


class SpreadModelName(StrEnum):
    OBSERVED_OR_FIXED = "OBSERVED_OR_FIXED"
    FIXED_BPS = "FIXED_BPS"


@dataclass(frozen=True)
class ExecutionConfig:
    model: ExecutionModelName = ExecutionModelName.IDEAL
    spread_model: SpreadModelName = SpreadModelName.OBSERVED_OR_FIXED
    fixed_spread_bps: float = 0.0
    slippage_bps: float = 0.0
    max_participation_rate: float = 1.0
    impact_coefficient_bps: float = 0.0
    latency_bars: int = 0
    version: str = "execution-v1"

    def __post_init__(self) -> None:
        if self.fixed_spread_bps < 0 or self.slippage_bps < 0 or self.impact_coefficient_bps < 0:
            raise ValueError("execution costs must be non-negative")
        if not 0 < self.max_participation_rate <= 1:
            raise ValueError("max_participation_rate must be in (0, 1]")
        if self.latency_bars < 0:
            raise ValueError("latency_bars must be non-negative")


@dataclass(frozen=True)
class MarketState:
    timestamp: datetime
    symbol: str
    bid: float
    ask: float
    mid: float
    last_price: float
    volume: int
    quote_source: str

    @property
    def spread(self) -> float:
        return self.ask - self.bid


@dataclass(frozen=True)
class ExecutionResult:
    order: OrderEvent
    fills: tuple[FillEvent, ...]
    rejected_quantity: float = 0.0


def market_state_from_event(event: MarketEvent, config: ExecutionConfig) -> MarketState:
    last_price = event.last_price if event.last_price is not None else event.open
    if (
        config.spread_model == SpreadModelName.OBSERVED_OR_FIXED
        and event.bid is not None
        and event.ask is not None
        and event.bid > 0
        and event.ask >= event.bid
    ):
        return MarketState(
            event.timestamp,
            event.symbol,
            event.bid,
            event.ask,
            (event.bid + event.ask) / 2,
            last_price,
            event.volume,
            "observed",
        )
    half_spread = last_price * config.fixed_spread_bps / 20_000.0
    return MarketState(
        event.timestamp,
        event.symbol,
        last_price - half_spread,
        last_price + half_spread,
        last_price,
        last_price,
        event.volume,
        "synthetic_fixed_bps",
    )


class ExecutionModel:
    def execute(
        self, order: OrderEvent, market: MarketState, config: ExecutionConfig
    ) -> ExecutionResult:
        raise NotImplementedError


class IdealExecution(ExecutionModel):
    def execute(
        self, order: OrderEvent, market: MarketState, config: ExecutionConfig
    ) -> ExecutionResult:
        return _execute(
            order,
            market,
            config,
            fill_quantity=order.quantity - order.filled_quantity,
            use_quote=False,
            use_impact=False,
        )


class BasicSlippageExecution(ExecutionModel):
    def execute(
        self, order: OrderEvent, market: MarketState, config: ExecutionConfig
    ) -> ExecutionResult:
        return _execute(
            order,
            market,
            config,
            fill_quantity=order.quantity - order.filled_quantity,
            use_quote=True,
            use_impact=False,
        )


class MicrostructureExecution(ExecutionModel):
    def execute(
        self, order: OrderEvent, market: MarketState, config: ExecutionConfig
    ) -> ExecutionResult:
        available = max(0.0, market.volume * config.max_participation_rate)
        return _execute(
            order,
            market,
            config,
            fill_quantity=min(order.quantity - order.filled_quantity, available),
            use_quote=True,
            use_impact=True,
        )


def execution_model_for(config: ExecutionConfig) -> ExecutionModel:
    if config.model == ExecutionModelName.IDEAL:
        return IdealExecution()
    if config.model == ExecutionModelName.BASIC_SLIPPAGE:
        return BasicSlippageExecution()
    return MicrostructureExecution()


def _execute(
    order: OrderEvent,
    market: MarketState,
    config: ExecutionConfig,
    *,
    fill_quantity: float,
    use_quote: bool,
    use_impact: bool,
) -> ExecutionResult:
    if order.status not in {OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED}:
        raise ValueError("execution model only fills submitted orders")
    remaining = max(0.0, order.quantity - order.filled_quantity)
    if fill_quantity <= 0 or remaining <= 0:
        return ExecutionResult(order=order, fills=())
    reference = (
        market.ask
        if use_quote and order.side == OrderSide.BUY
        else market.bid
        if use_quote
        else market.mid
    )
    signed = 1 if order.side == OrderSide.BUY else -1
    slippage = reference * config.slippage_bps / 10_000.0
    participation = fill_quantity / max(float(market.volume), 1.0)
    impact = (
        market.mid * config.impact_coefficient_bps / 10_000.0 * participation**0.5
        if use_impact
        else 0.0
    )
    price = reference + signed * (slippage + impact)
    total_filled = order.filled_quantity + fill_quantity
    status = (
        OrderStatus.FILLED
        if total_filled + 1e-9 >= order.quantity
        else OrderStatus.PARTIALLY_FILLED
    )
    average_fill_price = (
        order.average_fill_price * order.filled_quantity + price * fill_quantity
    ) / total_filled
    updated = OrderEvent(
        **{
            **order.__dict__,
            "filled_quantity": total_filled,
            "average_fill_price": average_fill_price,
            "status": status,
        }
    )
    gross = price * fill_quantity
    fill = FillEvent(
        order.session_id,
        new_id(),
        order.order_id,
        order.strategy_id,
        order.symbol,
        order.side,
        fill_quantity,
        round(price, 8),
        round(gross, 8),
        0.0,
        round(abs(price - market.mid) * fill_quantity, 8),
        market.timestamp,
        round(abs(reference - market.mid) * fill_quantity, 8),
        round(impact * fill_quantity, 8),
    )
    return ExecutionResult(order=updated, fills=(fill,))
