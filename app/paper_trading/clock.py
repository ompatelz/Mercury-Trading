from dataclasses import dataclass
from datetime import UTC, datetime, time
from enum import StrEnum


class MarketSessionState(StrEnum):
    PRE_MARKET = "PRE_MARKET"
    OPEN = "OPEN"
    CLOSED = "CLOSED"


@dataclass(frozen=True)
class MarketClock:
    open_time_utc: time = time(13, 30)
    close_time_utc: time = time(20, 0)

    def state_at(self, timestamp: datetime) -> MarketSessionState:
        current = timestamp.astimezone(UTC)
        if current.weekday() >= 5:
            return MarketSessionState.CLOSED
        current_time = current.time()
        if current_time < self.open_time_utc:
            return MarketSessionState.PRE_MARKET
        if current_time <= self.close_time_utc:
            return MarketSessionState.OPEN
        return MarketSessionState.CLOSED

    def can_submit_orders(self, timestamp: datetime) -> bool:
        return self.state_at(timestamp) == MarketSessionState.OPEN
