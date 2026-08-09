import math

import polars as pl
import pytest

from app.backtesting.engine import run_moving_average_backtest
from app.backtesting.metrics import (
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
    total_return,
    volatility,
)
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


def test_backtest_executes_prior_close_signal_at_current_open() -> None:
    result = run_moving_average_backtest(trend_bars(), 2, 3, 10_000, 0.0, 0.0)
    signals = moving_average_crossover_signals(trend_bars(), short_window=2, long_window=3)
    raw_signal = (
        signals.with_columns(
            (pl.col("short_ma") > pl.col("long_ma")).cast(pl.Float64).alias("raw_signal")
        )
        .get_column("raw_signal")
        .to_list()
    )

    first_buy = result.trades[0]
    first_buy_index = trend_bars().get_column("timestamp").to_list().index(first_buy.timestamp)

    assert raw_signal[first_buy_index - 1] == 1.0
    assert first_buy.price == trend_bars().row(first_buy_index, named=True)["open"]


def test_backtest_does_not_trade_on_same_bar_signal() -> None:
    bars = trend_bars()
    result = run_moving_average_backtest(bars, 2, 3, 10_000, 0.0, 0.0)
    signals = moving_average_crossover_signals(bars, short_window=2, long_window=3)
    raw_signal = (
        signals.with_columns(
            (pl.col("short_ma") > pl.col("long_ma")).cast(pl.Float64).alias("raw_signal")
        )
        .get_column("raw_signal")
        .to_list()
    )

    first_buy_index = bars.get_column("timestamp").to_list().index(result.trades[0].timestamp)

    assert raw_signal[first_buy_index] == 1.0
    assert result.trades[0].timestamp != bars.get_column("timestamp").to_list()[first_buy_index - 1]


def test_backtest_known_accounting_without_costs() -> None:
    result = run_moving_average_backtest(trend_bars(), 2, 3, 10_000, 0.0, 0.0)

    assert result.trades[0].side == "BUY"
    assert result.trades[0].quantity == pytest.approx(10_000 / 12)
    assert result.trades[0].price == 12
    assert result.trades[1].side == "SELL"
    assert result.trades[1].price == 16
    assert result.trades[1].realized_pnl == pytest.approx((10_000 / 12) * 16 - 10_000)


def test_backtest_applies_transaction_costs() -> None:
    no_cost = run_moving_average_backtest(trend_bars(), 2, 3, 10_000, 0.0)
    with_cost = run_moving_average_backtest(trend_bars(), 2, 3, 10_000, 10.0)

    assert with_cost.metrics["ending_portfolio_value"] < no_cost.metrics["ending_portfolio_value"]
    assert with_cost.metrics["number_of_trades"] > 0
    assert with_cost.metrics["transaction_costs"] > 0


def test_backtest_applies_slippage() -> None:
    no_slippage = run_moving_average_backtest(trend_bars(), 2, 3, 10_000, 0.0, 0.0)
    with_slippage = run_moving_average_backtest(trend_bars(), 2, 3, 10_000, 0.0, 25.0)

    assert (
        with_slippage.metrics["ending_portfolio_value"]
        < no_slippage.metrics["ending_portfolio_value"]
    )
    assert with_slippage.metrics["slippage_costs"] > 0


def test_backtest_records_buy_and_sell_trades() -> None:
    result = run_moving_average_backtest(trend_bars(), 2, 3, 10_000, 1.0, 2.0)

    assert result.trades
    assert {trade.side for trade in result.trades}.issubset({"BUY", "SELL"})
    assert result.metrics["number_of_trades"] == len(result.trades)
    assert result.metadata["candles_processed"] == trend_bars().height


def test_metric_calculations() -> None:
    equity = pl.Series([100.0, 110.0, 105.0, 120.0])
    returns = pl.Series([0.0, 0.10, -0.0454545, 0.142857])

    assert math.isclose(total_return(equity), 0.20)
    assert max_drawdown(equity) < 0.0
    assert sharpe_ratio(returns) != 0.0
    assert sortino_ratio(returns) == 0.0
    assert volatility(returns) > 0.0


def test_backtest_known_end_to_end_metrics_without_costs() -> None:
    result = run_moving_average_backtest(trend_bars(), 2, 3, 10_000, 0.0, 0.0)

    assert result.metrics["number_of_trades"] == 3
    assert result.metrics["transaction_costs"] == 0.0
    assert result.metrics["slippage_costs"] == 0.0
    assert result.metrics["ending_equity"] == pytest.approx(13_333.333333333334)
    assert result.metrics["total_return"] == pytest.approx(1 / 3)
