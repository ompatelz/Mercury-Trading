from app.paper_trading.events import MarketEvent, SignalDirection, SignalEvent, new_id
from app.paper_trading.portfolio import Portfolio


class MovingAverageSignalStrategy:
    def __init__(self, *, fast_window: int, slow_window: int, target_exposure_pct: float) -> None:
        if fast_window >= slow_window:
            raise ValueError("fast_window must be less than slow_window")
        self.fast_window = fast_window
        self.slow_window = slow_window
        self.target_exposure_pct = target_exposure_pct
        self.strategy_id = "moving_average_crossover"
        self._history: list[MarketEvent] = []

    def on_market(self, event: MarketEvent, portfolio: Portfolio) -> SignalEvent:
        if len(self._history) < self.slow_window:
            return self._signal(event, SignalDirection.HOLD, 0.0, "warming up")

        closes = [item.close for item in self._history]
        fast_ma = sum(closes[-self.fast_window :]) / self.fast_window
        slow_ma = sum(closes[-self.slow_window :]) / self.slow_window
        current_quantity = portfolio.position_quantity(event.symbol)
        target_quantity = 0.0
        direction = SignalDirection.HOLD
        reason = "moving averages unchanged"
        if fast_ma > slow_ma and current_quantity <= 1e-9:
            target_notional = portfolio.equity() * self.target_exposure_pct
            target_quantity = target_notional / event.open if event.open else 0.0
            direction = SignalDirection.BUY
            reason = "fast moving average crossed above slow moving average"
        elif fast_ma <= slow_ma and current_quantity > 0.0:
            target_quantity = current_quantity
            direction = SignalDirection.EXIT
            reason = "fast moving average is below or equal to slow moving average"

        return self._signal(
            event,
            direction,
            target_quantity,
            reason,
            {
                "fast_ma": round(fast_ma, 8),
                "slow_ma": round(slow_ma, 8),
                "history_bars": len(self._history),
                "last_history_timestamp": self._history[-1].timestamp.isoformat(),
            },
        )

    def observe(self, event: MarketEvent) -> None:
        self._history.append(event)

    @property
    def history_size(self) -> int:
        return len(self._history)

    def _signal(
        self,
        event: MarketEvent,
        direction: SignalDirection,
        quantity: float,
        reason: str,
        metadata: dict[str, object] | None = None,
    ) -> SignalEvent:
        return SignalEvent(
            session_id=event.session_id,
            signal_id=new_id(),
            strategy_id=self.strategy_id,
            symbol=event.symbol,
            timestamp=event.timestamp,
            direction=direction,
            strength=1.0 if direction != SignalDirection.HOLD else 0.0,
            intended_quantity=round(quantity, 8),
            reason=reason,
            metadata=metadata or {"history_bars": len(self._history)},
        )
