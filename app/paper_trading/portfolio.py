from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.paper_trading.events import FillEvent, OrderSide, PortfolioEvent


@dataclass
class Position:
    quantity: float = 0.0
    average_entry_price: float = 0.0

    @property
    def market_value(self) -> float:
        return self.quantity * self.average_entry_price


class Portfolio:
    def __init__(self, initial_cash: float) -> None:
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions: dict[str, Position] = {}
        self.realized_pnl = 0.0
        self.transaction_costs = 0.0
        self._last_prices: dict[str, float] = {}

    def position_quantity(self, symbol: str) -> float:
        return self.positions.get(symbol.upper(), Position()).quantity

    def apply_fill(self, fill: FillEvent) -> None:
        symbol = fill.symbol.upper()
        position = self.positions.setdefault(symbol, Position())
        self.transaction_costs += fill.fees
        self._last_prices[symbol] = fill.price
        if fill.side == OrderSide.BUY:
            previous_cost = position.quantity * position.average_entry_price
            new_cost = previous_cost + fill.gross_notional
            position.quantity += fill.quantity
            position.average_entry_price = (
                new_cost / position.quantity if position.quantity else 0.0
            )
            self.cash -= fill.gross_notional + fill.fees
            return

        sell_quantity = min(fill.quantity, position.quantity)
        self.realized_pnl += (fill.price - position.average_entry_price) * sell_quantity - fill.fees
        position.quantity -= sell_quantity
        self.cash += fill.gross_notional - fill.fees
        if position.quantity <= 1e-9:
            position.quantity = 0.0
            position.average_entry_price = 0.0

    def mark_price(self, symbol: str, price: float) -> None:
        self._last_prices[symbol.upper()] = price

    def equity(self) -> float:
        return self.cash + sum(
            position.quantity * self._last_prices.get(symbol, position.average_entry_price)
            for symbol, position in self.positions.items()
        )

    def exposure(self) -> float:
        return sum(
            abs(position.quantity * self._last_prices.get(symbol, position.average_entry_price))
            for symbol, position in self.positions.items()
        )

    def unrealized_pnl(self) -> float:
        return sum(
            (
                self._last_prices.get(symbol, position.average_entry_price)
                - position.average_entry_price
            )
            * position.quantity
            for symbol, position in self.positions.items()
        )

    def snapshot(self, session_id: UUID, timestamp: datetime) -> PortfolioEvent:
        return PortfolioEvent(
            session_id=session_id,
            timestamp=timestamp,
            cash=round(self.cash, 8),
            positions={
                symbol: {
                    "quantity": round(position.quantity, 8),
                    "average_entry_price": round(position.average_entry_price, 8),
                    "market_price": round(
                        self._last_prices.get(symbol, position.average_entry_price), 8
                    ),
                    "market_value": round(
                        position.quantity
                        * self._last_prices.get(symbol, position.average_entry_price),
                        8,
                    ),
                }
                for symbol, position in self.positions.items()
                if position.quantity > 0.0
            },
            realized_pnl=round(self.realized_pnl, 8),
            unrealized_pnl=round(self.unrealized_pnl(), 8),
            equity=round(self.equity(), 8),
            exposure=round(self.exposure(), 8),
            transaction_costs=round(self.transaction_costs, 8),
        )
