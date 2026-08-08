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
        frame.columns = [
            "_".join(str(part) for part in col if part) if isinstance(col, tuple) else str(col)
            for col in frame.columns
        ]
        return pl.from_pandas(frame)
