from app.paper_trading.events import FillEvent, MarketEvent, OrderEvent
from app.paper_trading.execution import (
    ExecutionConfig,
    ExecutionResult,
    execution_model_for,
    market_state_from_event,
)


class Broker:
    def execute(self, order: OrderEvent, market: MarketEvent) -> ExecutionResult:
        raise NotImplementedError


class PaperBroker(Broker):
    def __init__(
        self,
        *,
        commission_bps: float,
        slippage_bps: float,
        execution_config: ExecutionConfig | None = None,
    ) -> None:
        self.commission_rate = commission_bps / 10_000.0
        self.execution_config = execution_config or ExecutionConfig(slippage_bps=slippage_bps)

    def execute(self, order: OrderEvent, market: MarketEvent) -> ExecutionResult:
        result = execution_model_for(self.execution_config).execute(
            order, market_state_from_event(market, self.execution_config), self.execution_config
        )
        fills = tuple(
            FillEvent(
                **{**fill.__dict__, "fees": round(fill.gross_notional * self.commission_rate, 8)}
            )
            for fill in result.fills
        )
        return ExecutionResult(
            order=result.order, fills=fills, rejected_quantity=result.rejected_quantity
        )

    def submit_order(self, order: OrderEvent, market_price: float) -> FillEvent:
        market = MarketEvent(
            order.session_id,
            order.created_at,
            order.symbol,
            "synthetic",
            market_price,
            market_price,
            market_price,
            market_price,
            10**12,
            0,
        )
        result = self.execute(order, market)
        if not result.fills:
            raise ValueError("paper broker could not fill order")
        return result.fills[0]
