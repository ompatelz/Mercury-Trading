from datetime import date

import polars as pl
import yfinance as yf

from app.core.config import get_settings
from app.market_data.provider import MarketDataProvider


class YahooFinanceProvider(MarketDataProvider):
    def fetch_bars(self, symbol: str, start: date, end: date, interval: str) -> pl.DataFrame:
        settings = get_settings()
        frame = yf.download(
            tickers=symbol,
            start=start.isoformat(),
            end=end.isoformat(),
            interval=interval,
            auto_adjust=settings.yahoo_auto_adjust,
            progress=False,
        )
        if frame.empty:
            return pl.DataFrame()

        frame = frame.reset_index()
        # yfinance returns MultiIndex columns even for one ticker (for example,
        # ("Close", "MSFT")). Mercury operates on one requested symbol at a time,
        # so the market-field level is the canonical column name.
        frame.columns = [
            str(column[0]) if isinstance(column, tuple) else str(column)
            for column in frame.columns
        ]
        if "index" in frame.columns:
            frame = frame.rename(columns={"index": "Date"})

        # Avoid ``pl.from_pandas`` here: pandas extension dtypes can require the
        # optional pyarrow package in a slim runtime image. A Python-record
        # conversion gives Polars the normalized primitives directly instead.
        return pl.DataFrame(frame.to_dict(orient="list"))
