from typing import Protocol

import polars as pl

from app.strategy_dsl.compiler import evaluate_positions
from app.strategy_dsl.schemas import moving_average_crossover_spec


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
    if bars.height < long_window + 1:
        raise ValueError("not enough bars for the requested moving-average windows")
    spec = moving_average_crossover_spec({"fast_window": short_window, "slow_window": long_window})
    # The common DSL interpreter is the only signal-generation path for the
    # registered family; engine loops receive a point-in-time-safe position column.
    return evaluate_positions(spec, bars).rename({"fast_ma": "short_ma", "slow_ma": "long_ma"})
