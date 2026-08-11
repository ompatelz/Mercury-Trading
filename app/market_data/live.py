import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

import yfinance as yf

from app.core.config import get_settings
from app.market_data.normalization import MarketDataValidationError


class LiveFeedState(StrEnum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    STREAMING = "STREAMING"
    RECONNECTING = "RECONNECTING"
    FAILED = "FAILED"
    STOPPED = "STOPPED"


@dataclass(frozen=True)
class LiveMarketBar:
    symbol: str
    timestamp: datetime
    interval: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    source: str


class LiveMarketDataProvider(Protocol):
    source: str

    def stream_bars(
        self,
        *,
        symbol: str,
        interval: str,
        stop_requested: object | None = None,
    ) -> Iterator[LiveMarketBar]:
        """Yield normalized live bars for a symbol."""


class StaticLiveMarketDataProvider:
    source = "static"

    def __init__(self, bars: Iterable[LiveMarketBar], *, fail_after: int | None = None) -> None:
        self.bars = list(bars)
        self.fail_after = fail_after
        self._offset = 0
        self._failed_once = False

    def stream_bars(
        self,
        *,
        symbol: str,
        interval: str,
        stop_requested: object | None = None,
    ) -> Iterator[LiveMarketBar]:
        for index, bar in enumerate(self.bars[self._offset :], start=self._offset + 1):
            if self.fail_after is not None and index > self.fail_after and not self._failed_once:
                self._failed_once = True
                raise ConnectionError("static live feed disconnected")
            if _is_stop_requested(stop_requested):
                return
            if bar.symbol.upper() == symbol.upper() and bar.interval == interval:
                self._offset = index
                yield bar


class YahooFinanceLiveMarketDataProvider:
    source = "yahoo"

    def __init__(self, *, poll_seconds: float | None = None) -> None:
        settings = get_settings()
        self.poll_seconds = (
            poll_seconds if poll_seconds is not None else settings.live_market_data_poll_seconds
        )

    def stream_bars(
        self,
        *,
        symbol: str,
        interval: str,
        stop_requested: object | None = None,
    ) -> Iterator[LiveMarketBar]:
        seen_timestamps: set[datetime] = set()
        while not _is_stop_requested(stop_requested):
            frame = yf.download(
                tickers=symbol,
                period="1d",
                interval=interval,
                auto_adjust=get_settings().yahoo_auto_adjust,
                progress=False,
            )
            if not frame.empty:
                frame = frame.reset_index()
                frame.columns = [
                    "_".join(str(part) for part in col if part)
                    if isinstance(col, tuple)
                    else str(col)
                    for col in frame.columns
                ]
                for row in frame.to_dict("records"):
                    bar = live_bar_from_mapping(
                        row,
                        symbol=symbol,
                        interval=interval,
                        source=self.source,
                    )
                    if bar.timestamp not in seen_timestamps:
                        seen_timestamps.add(bar.timestamp)
                        yield bar
            time.sleep(self.poll_seconds)


def live_bar_from_mapping(
    payload: dict[str, object],
    *,
    symbol: str,
    interval: str,
    source: str,
) -> LiveMarketBar:
    timestamp = payload.get("timestamp") or payload.get("Date") or payload.get("Datetime")
    open_price = payload.get("open") or payload.get("Open")
    high = payload.get("high") or payload.get("High")
    low = payload.get("low") or payload.get("Low")
    close = payload.get("close") or payload.get("Close") or payload.get("Adj Close")
    volume = payload.get("volume") or payload.get("Volume")
    if any(value is None for value in [timestamp, open_price, high, low, close, volume]):
        raise MarketDataValidationError("live market event missing required OHLCV fields")
    parsed = _to_utc_datetime(timestamp)
    normalized = LiveMarketBar(
        symbol=symbol.upper(),
        timestamp=parsed,
        interval=interval,
        open=_to_float(open_price),
        high=_to_float(high),
        low=_to_float(low),
        close=_to_float(close),
        volume=_to_int(volume),
        source=source,
    )
    validate_live_bar(normalized)
    return normalized


def validate_live_bar(bar: LiveMarketBar) -> None:
    if bar.volume < 0:
        raise MarketDataValidationError("live market event contains negative volume")
    if min(bar.open, bar.high, bar.low, bar.close) <= 0:
        raise MarketDataValidationError("live market event contains non-positive OHLC values")
    if bar.high < max(bar.open, bar.close, bar.low) or bar.low > min(bar.open, bar.close, bar.high):
        raise MarketDataValidationError("live market event violates OHLC consistency")


def _to_utc_datetime(value: object) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _to_float(value: object) -> float:
    if isinstance(value, int | float | str):
        return float(value)
    raise MarketDataValidationError(f"live market event contains non-numeric value: {value}")


def _to_int(value: object) -> int:
    if isinstance(value, int | float | str):
        return int(value)
    raise MarketDataValidationError(f"live market event contains non-integer value: {value}")


def _is_stop_requested(stop_requested: object | None) -> bool:
    return bool(
        stop_requested is not None and hasattr(stop_requested, "is_set") and stop_requested.is_set()
    )
