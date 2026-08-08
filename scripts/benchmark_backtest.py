from __future__ import annotations

import argparse
import time
from datetime import UTC, datetime, timedelta

import polars as pl

from app.backtesting.engine import run_moving_average_backtest


def synthetic_bars(rows: int) -> pl.DataFrame:
    start = datetime(2020, 1, 1, tzinfo=UTC)
    closes = [100.0 + index * 0.01 + (index % 17) * 0.05 for index in range(rows)]
    return pl.DataFrame(
        {
            "timestamp": [start + timedelta(days=index) for index in range(rows)],
            "open": closes,
            "high": [price * 1.01 for price in closes],
            "low": [price * 0.99 for price in closes],
            "close": closes,
            "volume": [1_000_000] * rows,
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark the Python moving-average backtester.")
    parser.add_argument("--rows", type=int, default=10_000)
    args = parser.parse_args()

    bars = synthetic_bars(args.rows)
    started = time.perf_counter()
    result = run_moving_average_backtest(
        bars=bars,
        short_window=20,
        long_window=50,
        initial_capital=10_000.0,
        transaction_cost_bps=1.0,
        slippage_bps=1.0,
    )
    duration = time.perf_counter() - started
    rows_per_second = args.rows / duration if duration else float("inf")
    print(
        {
            "rows": args.rows,
            "duration_seconds": round(duration, 6),
            "rows_per_second": round(rows_per_second, 2),
            "trades": result.metrics["number_of_trades"],
            "ending_portfolio_value": round(result.metrics["ending_portfolio_value"], 2),
        }
    )


if __name__ == "__main__":
    main()
