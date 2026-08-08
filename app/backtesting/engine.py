from dataclasses import dataclass

import polars as pl

from app.backtesting.metrics import annualized_return, max_drawdown, sharpe_ratio, total_return
from app.backtesting.strategy import moving_average_crossover_signals


@dataclass(frozen=True)
class BacktestResult:
    equity_curve: pl.DataFrame
    metrics: dict[str, float | int]


def run_moving_average_backtest(
    bars: pl.DataFrame,
    short_window: int,
    long_window: int,
    initial_capital: float,
    transaction_cost_bps: float,
) -> BacktestResult:
    prepared = moving_average_crossover_signals(bars, short_window, long_window)
    cost_rate = transaction_cost_bps / 10_000.0
    equity_curve = (
        prepared.with_columns(
            pl.col("close").pct_change().fill_null(0.0).alias("asset_return"),
            pl.col("position").diff().abs().fill_null(pl.col("position")).alias("trade_size"),
        )
        .with_columns(
            (pl.col("position") * pl.col("asset_return") - pl.col("trade_size") * cost_rate).alias(
                "strategy_return"
            )
        )
        .with_columns(
            (initial_capital * (1.0 + pl.col("strategy_return")).cum_prod()).alias("equity")
        )
    )

    trades = int(equity_curve.filter(pl.col("trade_size") > 0).height)
    turnover = float(equity_curve.get_column("trade_size").sum() or 0.0)
    metrics: dict[str, float | int] = {
        "total_return": total_return(equity_curve.get_column("equity")),
        "annualized_return": annualized_return(equity_curve.get_column("equity")),
        "sharpe_ratio": sharpe_ratio(equity_curve.get_column("strategy_return")),
        "max_drawdown": max_drawdown(equity_curve.get_column("equity")),
        "number_of_trades": trades,
        "turnover": turnover,
        "ending_equity": float(equity_curve.get_column("equity")[-1]),
    }
    return BacktestResult(equity_curve=equity_curve, metrics=metrics)
