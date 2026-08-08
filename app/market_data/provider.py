from datetime import date
from typing import Protocol

import polars as pl


class MarketDataProvider(Protocol):
    def fetch_bars(self, symbol: str, start: date, end: date, interval: str) -> pl.DataFrame:
        """Fetch raw market bars for the requested symbol and time range."""
