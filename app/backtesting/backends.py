"""Selectable deterministic backtesting engines; Python is the correctness oracle."""

from __future__ import annotations

from importlib import import_module
from time import perf_counter
from typing import Protocol, cast

import numpy as np
import polars as pl

from app.backtesting.engine import BacktestResult, BacktestTrade, run_moving_average_backtest
from app.backtesting.metrics import (
    annualized_return,
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
    total_return,
    volatility,
    win_rate,
)
from app.backtesting.strategy import moving_average_crossover_signals


class BacktestEngine(Protocol):
    name: str
    version: str

    def run_moving_average(
        self,
        bars: pl.DataFrame,
        short_window: int,
        long_window: int,
        initial_capital: float,
        transaction_cost_bps: float,
        slippage_bps: float,
    ) -> BacktestResult: ...


class PythonBacktestEngine:
    name = "python"
    version = "python-reference-v1"

    def run_moving_average(
        self,
        bars: pl.DataFrame,
        short_window: int,
        long_window: int,
        initial_capital: float,
        transaction_cost_bps: float,
        slippage_bps: float,
    ) -> BacktestResult:
        result = run_moving_average_backtest(
            bars, short_window, long_window, initial_capital, transaction_cost_bps, slippage_bps
        )
        return BacktestResult(
            result.equity_curve,
            result.trades,
            result.metrics,
            {**result.metadata, "engine": self.name, "engine_version": self.version},
        )


class CppBacktestEngine:
    name = "cpp"
    version = "cpp-execution-v2"

    def run_moving_average(
        self,
        bars: pl.DataFrame,
        short_window: int,
        long_window: int,
        initial_capital: float,
        transaction_cost_bps: float,
        slippage_bps: float,
    ) -> BacktestResult:
        started = perf_counter()
        prepared = moving_average_crossover_signals(bars, short_window, long_window)
        native = import_module("app.backtesting.native._engine")
        raw = cast(
            dict[str, object],
            native.run_long_only_execution(
                prepared.get_column("timestamp").to_list(),
                _contiguous(prepared, "open"),
                _contiguous(prepared, "close"),
                _contiguous(prepared, "position"),
                initial_capital,
                transaction_cost_bps,
                slippage_bps,
            ),
        )
        timestamps = prepared.get_column("timestamp").to_list()
        if "equity_curve" in raw:
            equity_curve = pl.DataFrame(cast(list[dict[str, object]], raw["equity_curve"]))
            equity_curve = equity_curve.with_columns(
                pl.col("equity").pct_change().fill_null(0.0).alias("strategy_return")
            )
            equity = np.asarray(equity_curve.get_column("equity").to_numpy(), dtype=np.float64)
        else:
            equity = np.asarray(raw["equity"], dtype=np.float64)
            equity_curve = prepared.with_columns(
                pl.Series("cash", np.asarray(raw["cash"], dtype=np.float64)),
                pl.Series("shares", np.asarray(raw["shares"], dtype=np.float64)),
                pl.Series("trade_size", np.asarray(raw["trade_size"], dtype=np.float64)),
                pl.Series(
                    "transaction_cost", np.asarray(raw["transaction_cost"], dtype=np.float64)
                ),
                pl.Series("slippage_cost", np.asarray(raw["slippage_cost"], dtype=np.float64)),
                pl.Series("equity", equity),
            ).with_columns(pl.col("equity").pct_change().fill_null(0.0).alias("strategy_return"))
        trades = [_trade(row, timestamps) for row in cast(list[dict[str, object]], raw["trades"])]
        returns, equity_series = (
            equity_curve.get_column("strategy_return"),
            equity_curve.get_column("equity"),
        )
        native_metrics = cast(dict[str, float | int], raw["metrics"])
        closed_pnls = [trade.realized_pnl for trade in trades if trade.realized_pnl is not None]
        metrics: dict[str, float | int] = {
            "total_return": total_return(equity_series),
            "annualized_return": annualized_return(equity_series),
            "sharpe_ratio": sharpe_ratio(returns),
            "sortino_ratio": sortino_ratio(returns),
            "max_drawdown": max_drawdown(equity_series),
            "volatility": volatility(returns),
            "win_rate": win_rate(closed_pnls),
            **native_metrics,
            "ending_equity": float(equity[-1]),
        }
        return BacktestResult(
            equity_curve,
            trades,
            metrics,
            {
                "duration_ms": (perf_counter() - started) * 1000.0,
                "candles_processed": prepared.height,
                "strategy_name": "moving_average_crossover",
                "dataset_size": prepared.height,
                "engine": self.name,
                "engine_version": self.version,
                "input_dtype": "float64",
                "input_layout": "contiguous",
            },
        )


def get_backtest_engine(name: str) -> BacktestEngine:
    normalized = name.lower().strip()
    if normalized == "python":
        return PythonBacktestEngine()
    if normalized == "cpp":
        return CppBacktestEngine()
    raise ValueError("BACKTEST_ENGINE must be either 'python' or 'cpp'")


def _contiguous(frame: pl.DataFrame, name: str) -> np.ndarray[tuple[int], np.dtype[np.float64]]:
    return np.ascontiguousarray(frame.get_column(name).to_numpy(), dtype=np.float64)


def _trade(row: dict[str, object], timestamps: list[object]) -> BacktestTrade:
    timestamp = row.get("timestamp")
    if timestamp is None:
        index = int(cast(int, row["index"]))
        timestamp = timestamps[index]
    realized_pnl = row["realized_pnl"]
    return BacktestTrade(
        cast(str, timestamp),
        cast(str, row["side"]),
        float(cast(float, row["quantity"])),
        float(cast(float, row["price"])),
        float(cast(float, row["notional"])),
        float(cast(float, row["transaction_cost"])),
        float(cast(float, row["slippage_cost"])),
        cast(float, realized_pnl) if realized_pnl is not None else None,
    )
