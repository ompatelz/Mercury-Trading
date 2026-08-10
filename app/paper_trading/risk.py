from dataclasses import dataclass, field

from app.paper_trading.events import OrderEvent, OrderSide, OrderStatus
from app.paper_trading.portfolio import Portfolio


@dataclass(frozen=True)
class RiskConfig:
    max_position_quantity: float = 1_000_000.0
    max_order_value: float = 1_000_000.0
    max_gross_exposure_pct: float = 1.0
    commission_bps: float = 0.0
    slippage_bps: float = 0.0


@dataclass
class RiskEngine:
    config: RiskConfig
    seen_orders: set[tuple[str, str, object, str, float]] = field(default_factory=set)

    def check(self, order: OrderEvent, portfolio: Portfolio, market_price: float) -> OrderEvent:
        reason = self._rejection_reason(order, portfolio, market_price)
        if reason is not None:
            return OrderEvent(
                session_id=order.session_id,
                order_id=order.order_id,
                strategy_id=order.strategy_id,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                created_at=order.created_at,
                status=OrderStatus.REJECTED,
                reason=reason,
            )
        key = (
            order.strategy_id,
            order.symbol,
            order.created_at,
            order.side.value,
            round(order.quantity, 8),
        )
        self.seen_orders.add(key)
        return OrderEvent(
            session_id=order.session_id,
            order_id=order.order_id,
            strategy_id=order.strategy_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            created_at=order.created_at,
            status=OrderStatus.SUBMITTED,
        )

    def _rejection_reason(
        self, order: OrderEvent, portfolio: Portfolio, market_price: float
    ) -> str | None:
        if order.quantity <= 0.0:
            return "invalid quantity"
        notional = order.quantity * market_price
        estimated_cash_required = self._estimated_cash_required(order, market_price)
        if notional > self.config.max_order_value:
            return "maximum order value exceeded"
        key = (
            order.strategy_id,
            order.symbol,
            order.created_at,
            order.side.value,
            round(order.quantity, 8),
        )
        if key in self.seen_orders:
            return "duplicate order"
        current_quantity = portfolio.position_quantity(order.symbol)
        projected_quantity = (
            current_quantity + order.quantity
            if order.side == OrderSide.BUY
            else current_quantity - order.quantity
        )
        if projected_quantity < -1e-9:
            return "insufficient position"
        if abs(projected_quantity) > self.config.max_position_quantity:
            return "maximum position size exceeded"
        if order.side == OrderSide.BUY and estimated_cash_required > portfolio.cash:
            return "insufficient cash"
        projected_exposure = portfolio.exposure() - abs(current_quantity * market_price)
        projected_exposure += abs(projected_quantity * market_price)
        if projected_exposure > portfolio.equity() * self.config.max_gross_exposure_pct:
            return "maximum portfolio exposure exceeded"
        return None

    def _estimated_cash_required(self, order: OrderEvent, market_price: float) -> float:
        if order.side != OrderSide.BUY:
            return 0.0
        slippage_rate = self.config.slippage_bps / 10_000.0
        commission_rate = self.config.commission_bps / 10_000.0
        fill_notional = order.quantity * market_price * (1.0 + slippage_rate)
        return fill_notional * (1.0 + commission_rate)
