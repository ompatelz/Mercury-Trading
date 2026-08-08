from datetime import UTC, datetime

import polars as pl

REQUIRED_COLUMNS = {"timestamp", "open", "high", "low", "close", "volume"}
PROVIDER_COLUMN_MAP = {
    "Date": "timestamp",
    "Datetime": "timestamp",
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "close",
    "Volume": "volume",
}


class MarketDataValidationError(ValueError):
    pass


def normalize_bars(raw: pl.DataFrame, symbol: str, interval: str) -> pl.DataFrame:
    if raw.is_empty():
        raise MarketDataValidationError("market data provider returned no rows")

    renamed = raw.rename(
        {
            column: PROVIDER_COLUMN_MAP[column]
            for column in raw.columns
            if column in PROVIDER_COLUMN_MAP
        }
    )
    missing = REQUIRED_COLUMNS - set(renamed.columns)
    if missing:
        raise MarketDataValidationError(f"missing required market data columns: {sorted(missing)}")

    normalized = (
        renamed.select("timestamp", "open", "high", "low", "close", "volume")
        .with_columns(
            pl.lit(symbol.upper()).alias("symbol"),
            pl.lit(interval).alias("interval"),
            pl.col("timestamp").map_elements(
                _to_utc_datetime, return_dtype=pl.Datetime(time_zone="UTC")
            ),
            pl.col("open").cast(pl.Float64),
            pl.col("high").cast(pl.Float64),
            pl.col("low").cast(pl.Float64),
            pl.col("close").cast(pl.Float64),
            pl.col("volume").cast(pl.Int64),
        )
        .select("symbol", "timestamp", "interval", "open", "high", "low", "close", "volume")
        .sort("timestamp")
    )

    _validate_bars(normalized)
    return normalized


def _to_utc_datetime(value: object) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _validate_bars(bars: pl.DataFrame) -> None:
    if any(value > 0 for value in bars.null_count().row(0)):
        raise MarketDataValidationError("market data contains null values")
    if bars.get_column("timestamp").n_unique() != bars.height:
        raise MarketDataValidationError("market data contains duplicate timestamps")
    if bars.filter(pl.col("volume") < 0).height:
        raise MarketDataValidationError("market data contains negative volume")
    numeric_cols = ["open", "high", "low", "close"]
    if bars.filter(pl.any_horizontal([pl.col(column) <= 0 for column in numeric_cols])).height:
        raise MarketDataValidationError("market data contains non-positive OHLC values")
    if bars.filter(
        (pl.col("high") < pl.max_horizontal("open", "close", "low"))
        | (pl.col("low") > pl.min_horizontal("open", "close", "high"))
    ).height:
        raise MarketDataValidationError("market data violates OHLC consistency")
