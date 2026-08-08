from typing import Protocol

import polars as pl


class Strategy(Protocol):
    name: str

    def generate_signals(self, bars: pl.DataFrame) -> pl.DataFrame:
        """Return bars with a point-in-time safe position column."""


class MovingAverageCrossoverStrategy:
    name = "moving_average_crossover"

    def __init__(self, short_window: int, long_window: int) -> None:
        self.short_window = short_window
        self.long_window = long_window

    def generate_signals(self, bars: pl.DataFrame) -> pl.DataFrame:
        return moving_average_crossover_signals(bars, self.short_window, self.long_window)


def moving_average_crossover_signals(
    bars: pl.DataFrame, short_window: int, long_window: int
) -> pl.DataFrame:
    if short_window >= long_window:
        raise ValueError("short_window must be less than long_window")
    if bars.height < long_window + 1:
        raise ValueError("not enough bars for the requested moving-average windows")

    return bars.with_columns(
        pl.col("close").rolling_mean(short_window).alias("short_ma"),
        pl.col("close").rolling_mean(long_window).alias("long_ma"),
    ).with_columns(
        pl.when(pl.col("short_ma") > pl.col("long_ma"))
        .then(1.0)
        .otherwise(0.0)
        .shift(1)
        .fill_null(0.0)
        .alias("position")
    )
