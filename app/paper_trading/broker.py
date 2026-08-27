from app.paper_trading.events import FillEvent, OrderEvent, OrderSide, OrderStatus, new_id


class Broker:
    def submit_order(self, order: OrderEvent, market_price: float) -> FillEvent:
        raise NotImplementedError


class PaperBroker(Broker):
    def __init__(self, *, commission_bps: float, slippage_bps: float) -> None:
        self.commission_rate = commission_bps / 10_000.0
        self.slippage_rate = slippage_bps / 10_000.0

    def submit_order(self, order: OrderEvent, market_price: float) -> FillEvent:
        if order.status != OrderStatus.SUBMITTED:
            raise ValueError("paper broker only fills submitted orders")
        signed_slippage = self.slippage_rate if order.side == OrderSide.BUY else -self.slippage_rate
        fill_price = market_price * (1.0 + signed_slippage)
        gross_notional = fill_price * order.quantity
        fees = gross_notional * self.commission_rate
        slippage_cost = abs(fill_price - market_price) * order.quantity
        return FillEvent(
            session_id=order.session_id,
            fill_id=new_id(),
            order_id=order.order_id,
            strategy_id=order.strategy_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=round(fill_price, 8),
            gross_notional=round(gross_notional, 8),
            fees=round(fees, 8),
            slippage_cost=round(slippage_cost, 8),
            timestamp=order.created_at,
        )
