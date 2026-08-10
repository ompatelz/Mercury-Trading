from collections.abc import Iterator
from uuid import UUID

from app.models.market_data import MarketBar
from app.paper_trading.events import MarketEvent


class MarketDataStream:
    def events(self) -> Iterator[MarketEvent]:
        raise NotImplementedError


class HistoricalReplayStream(MarketDataStream):
    def __init__(self, *, session_id: UUID, bars: list[MarketBar]) -> None:
        self.session_id = session_id
        self.bars = sorted(bars, key=lambda item: item.timestamp)

    def events(self) -> Iterator[MarketEvent]:
        previous_timestamp = None
        for sequence, bar in enumerate(self.bars, start=1):
            if previous_timestamp is not None and bar.timestamp < previous_timestamp:
                raise ValueError("historical replay bars must be chronological")
            previous_timestamp = bar.timestamp
            yield MarketEvent(
                session_id=self.session_id,
                timestamp=bar.timestamp,
                symbol=bar.symbol.upper(),
                interval=bar.interval,
                open=float(bar.open),
                high=float(bar.high),
                low=float(bar.low),
                close=float(bar.close),
                volume=bar.volume,
                sequence=sequence,
            )
