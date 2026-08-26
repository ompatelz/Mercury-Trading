"""Repeatable Python/C++ backtesting benchmark; output is measured, never synthetic."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl

from app.backtesting.backends import get_backtest_engine


def synthetic_bars(rows: int) -> pl.DataFrame:
    start = datetime(2020, 1, 1, tzinfo=UTC)
    closes = [100.0 + index * 0.01 + (index % 17) * 0.05 for index in range(rows)]
    return pl.DataFrame(
        {
            "timestamp": [start + timedelta(minutes=index) for index in range(rows)],
            "open": closes,
            "high": [price * 1.01 for price in closes],
            "low": [price * 0.99 for price in closes],
            "close": closes,
            "volume": [1_000_000] * rows,
        }
    )


def measure(engine_name: str, bars: pl.DataFrame, repeats: int) -> dict[str, object]:
    engine = get_backtest_engine(engine_name)
    engine.run_moving_average(bars, 20, 50, 10_000.0, 1.0, 1.0)  # warm-up, excluded
    durations: list[float] = []
    for _ in range(repeats):
        started = time.perf_counter()
        result = engine.run_moving_average(bars, 20, 50, 10_000.0, 1.0, 1.0)
        durations.append(time.perf_counter() - started)
    median = statistics.median(durations)
    return {
        "engine": engine_name,
        "engine_version": engine.version,
        "rows": bars.height,
        "repeats": repeats,
        "median_seconds": median,
        "min_seconds": min(durations),
        "rows_per_second": bars.height / median,
        "trades": result.metrics["number_of_trades"],
        "ending_equity": result.metrics["ending_equity"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", nargs="+", type=int, default=[100_000, 1_000_000])
    parser.add_argument("--engines", nargs="+", default=["python", "cpp"])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    results = []
    for rows in args.rows:
        bars = synthetic_bars(rows)
        for engine in args.engines:
            results.append(measure(engine, bars, args.repeats))
    payload = {
        "schema_version": 1,
        "recorded_at": datetime.now(UTC).isoformat(),
        "platform": platform.platform(),
        "results": results,
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
