import polars as pl
import pytest

from app.market_data.normalization import MarketDataValidationError, normalize_bars
from tests.conftest import sample_raw_bars


def test_normalize_bars_standardizes_columns_and_symbol() -> None:
    bars = normalize_bars(sample_raw_bars(), symbol="msft", interval="1d")

    assert bars.columns == [
        "symbol",
        "timestamp",
        "interval",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]
    assert bars["symbol"].to_list() == ["MSFT"] * 10
    assert bars["interval"].to_list() == ["1d"] * 10


def test_normalize_bars_rejects_duplicate_timestamps() -> None:
    raw = sample_raw_bars().vstack(sample_raw_bars().head(1))

    with pytest.raises(MarketDataValidationError, match="duplicate timestamps"):
        normalize_bars(raw, symbol="MSFT", interval="1d")


def test_normalize_bars_rejects_invalid_ohlc_values() -> None:
    raw = sample_raw_bars().with_columns(pl.lit(90).alias("High"))

    with pytest.raises(MarketDataValidationError, match="OHLC consistency"):
        normalize_bars(raw, symbol="MSFT", interval="1d")
