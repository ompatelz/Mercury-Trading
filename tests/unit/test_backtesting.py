import math

import polars as pl

from app.backtesting.engine import run_moving_average_backtest
from app.backtesting.metrics import max_drawdown, sharpe_ratio, total_return
from app.backtesting.strategy import moving_average_crossover_signals


def trend_bars() -> pl.DataFrame:
    closes = [10, 10, 10, 11, 12, 13, 14, 15, 14, 13, 16, 18]
    return pl.DataFrame(
        {
            "timestamp": [f"2024-01-{day:02d}" for day in range(1, 13)],
            "open": closes,
            "high": [price + 1 for price in closes],
            "low": [price - 1 for price in closes],
            "close": closes,
            "volume": [1000] * len(closes),
        }
    )


def test_moving_average_signal_uses_prior_signal_for_position() -> None:
    signals = moving_average_crossover_signals(trend_bars(), short_window=2, long_window=3)
    raw_signal = (
        signals.with_columns(
            (pl.col("short_ma") > pl.col("long_ma")).cast(pl.Float64).alias("raw_signal")
        )
        .get_column("raw_signal")
        .to_list()
    )
    positions = signals.get_column("position").to_list()

    assert positions[0] == 0.0
    assert positions[4] == raw_signal[3]


def test_backtest_applies_transaction_costs() -> None:
    no_cost = run_moving_average_backtest(trend_bars(), 2, 3, 10_000, 0.0)
    with_cost = run_moving_average_backtest(trend_bars(), 2, 3, 10_000, 10.0)

    assert with_cost.metrics["ending_equity"] < no_cost.metrics["ending_equity"]
    assert with_cost.metrics["number_of_trades"] > 0


def test_metric_calculations() -> None:
    equity = pl.Series([100.0, 110.0, 105.0, 120.0])
    returns = pl.Series([0.0, 0.10, -0.0454545, 0.142857])

    assert math.isclose(total_return(equity), 0.20)
    assert max_drawdown(equity) < 0.0
    assert sharpe_ratio(returns) != 0.0
