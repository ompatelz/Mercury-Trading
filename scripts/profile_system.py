"""Capture repeatable local timings for Mercury's deterministic hot paths.

This is a profiling harness, not a benchmark claim.  Results are machine-local
and are emitted only when an explicit output path is supplied.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl
from fastapi.testclient import TestClient

from app.backtesting.backends import get_backtest_engine
from app.campaigns.optimization import generate_parameter_variants
from app.main import create_app
from app.strategy_dsl.compiler import evaluate_positions
from app.strategy_dsl.schemas import moving_average_crossover_spec
from app.stress_testing.engine import block_bootstrap, summarize_monte_carlo


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


def measure(name: str, operation: Callable[[], object], repeats: int) -> dict[str, Any]:
    operation()  # warm-up excluded from timing
    durations_ms: list[float] = []
    for _ in range(repeats):
        started = time.perf_counter()
        operation()
        durations_ms.append((time.perf_counter() - started) * 1000.0)
    return {
        "name": name,
        "repeats": repeats,
        "median_ms": round(statistics.median(durations_ms), 6),
        "p95_ms": round(_percentile(durations_ms, 0.95), 6),
        "min_ms": round(min(durations_ms), 6),
    }


def profile(rows: int, repeats: int) -> dict[str, Any]:
    bars = synthetic_bars(rows)
    engine = get_backtest_engine("python")
    spec = moving_average_crossover_spec({"fast_window": 20, "slow_window": 50})
    returns = [((index % 17) - 8) / 10_000 for index in range(rows)]
    payload = [
        {"timestamp": value.isoformat(), "close": float(index), "symbol": "MSFT"}
        for index, value in enumerate(bars.get_column("timestamp").head(min(rows, 5_000)))
    ]
    parameter_space = {
        "short_window": list(range(2, 42, 2)),
        "long_window": list(range(10, 90, 2)),
    }
    app = create_app()
    with TestClient(app) as client:
        operations: list[tuple[str, Callable[[], object]]] = [
            (
                "api_health",
                lambda: _require_success(client.get("/health").status_code),
            ),
            (
                "backtest_python",
                lambda: engine.run_moving_average(bars, 20, 50, 10_000.0, 1.0, 1.0),
            ),
            ("strategy_dsl_positions", lambda: evaluate_positions(spec, bars)),
            (
                "optimization_grid_generation",
                lambda: generate_parameter_variants(parameter_space, "grid", 500),
            ),
            (
                "monte_carlo_bootstrap",
                lambda: summarize_monte_carlo(
                    block_bootstrap(returns, block_size=10, simulations=100, seed=17)
                ),
            ),
            ("json_serialization", lambda: json.dumps(payload, separators=(",", ":"))),
        ]
        results = [measure(name, operation, repeats) for name, operation in operations]
    return {
        "schema_version": 1,
        "recorded_at": datetime.now(UTC).isoformat(),
        "platform": platform.platform(),
        "rows": rows,
        "results": results,
        "not_measured": {
            "database": "requires a separately provisioned PostgreSQL capture",
            "campaign_workers": "requires matched real worker-pool captures",
            "dashboard_queries": "requires production-shaped persisted data",
            "ml_training": "requires a versioned training dataset and model configuration",
        },
    }


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * quantile))
    return ordered[index]


def _require_success(status_code: int) -> None:
    if status_code != 200:
        raise RuntimeError(f"health request failed with {status_code}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile Mercury deterministic hot paths.")
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.rows < 100:
        raise ValueError("rows must be at least 100")
    if args.repeats < 1:
        raise ValueError("repeats must be positive")
    payload = profile(args.rows, args.repeats)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
