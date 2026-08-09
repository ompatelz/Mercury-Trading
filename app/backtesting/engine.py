import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

import polars as pl

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

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BacktestTrade:
    timestamp: datetime | str
    side: str
    quantity: float
    price: float
    notional: float
    transaction_cost: float
    slippage_cost: float
    realized_pnl: float | None


@dataclass(frozen=True)
class BacktestResult:
    equity_curve: pl.DataFrame
    trades: list[BacktestTrade]
    metrics: dict[str, float | int]
    metadata: dict[str, Any]


def run_moving_average_backtest(
    bars: pl.DataFrame,
    short_window: int,
    long_window: int,
    initial_capital: float,
    transaction_cost_bps: float,
    slippage_bps: float = 0.0,
) -> BacktestResult:
    started = time.perf_counter()
    prepared = moving_average_crossover_signals(bars, short_window, long_window)
    fee_rate = transaction_cost_bps / 10_000.0
    slippage_rate = slippage_bps / 10_000.0

    cash = initial_capital
    shares = 0.0
    entry_cost_basis = 0.0
    previous_position = 0.0
    equity_rows: list[dict[str, Any]] = []
    trades: list[BacktestTrade] = []
    closed_trade_pnls: list[float] = []
    turnover_notional = 0.0
    total_transaction_costs = 0.0
    total_slippage_costs = 0.0

    for row in prepared.iter_rows(named=True):
        timestamp = row["timestamp"]
        open_price = float(row["open"])
        close_price = float(row["close"])
        desired_position = float(row["position"])
        trade_size = abs(desired_position - previous_position)
        transaction_cost = 0.0
        slippage_cost = 0.0

        if desired_position > previous_position and cash > 0.0:
            execution_price = open_price * (1.0 + slippage_rate)
            shares = cash / (execution_price * (1.0 + fee_rate))
            notional = shares * execution_price
            transaction_cost = notional * fee_rate
            slippage_cost = shares * open_price * slippage_rate
            cash -= notional + transaction_cost
            entry_cost_basis = notional + transaction_cost
            turnover_notional += notional
            total_transaction_costs += transaction_cost
            total_slippage_costs += slippage_cost
            trades.append(
                BacktestTrade(
                    timestamp=timestamp,
                    side="BUY",
                    quantity=shares,
                    price=execution_price,
                    notional=notional,
                    transaction_cost=transaction_cost,
                    slippage_cost=slippage_cost,
                    realized_pnl=None,
                )
            )
        elif desired_position < previous_position and shares > 0.0:
            execution_price = open_price * (1.0 - slippage_rate)
            notional = shares * execution_price
            transaction_cost = notional * fee_rate
            slippage_cost = shares * open_price * slippage_rate
            realized_pnl = notional - transaction_cost - entry_cost_basis
            cash += notional - transaction_cost
            turnover_notional += notional
            total_transaction_costs += transaction_cost
            total_slippage_costs += slippage_cost
            closed_trade_pnls.append(realized_pnl)
            trades.append(
                BacktestTrade(
                    timestamp=timestamp,
                    side="SELL",
                    quantity=shares,
                    price=execution_price,
                    notional=notional,
                    transaction_cost=transaction_cost,
                    slippage_cost=slippage_cost,
                    realized_pnl=realized_pnl,
                )
            )
            shares = 0.0
            entry_cost_basis = 0.0

        current_equity = cash + shares * close_price
        equity_rows.append(
            {
                **row,
                "cash": cash,
                "shares": shares,
                "trade_size": trade_size,
                "transaction_cost": transaction_cost,
                "slippage_cost": slippage_cost,
                "equity": current_equity,
            }
        )
        previous_position = desired_position

    equity_curve = pl.DataFrame(equity_rows).with_columns(
        pl.col("equity").pct_change().fill_null(0.0).alias("strategy_return")
    )

    returns = equity_curve.get_column("strategy_return")
    equity_series = equity_curve.get_column("equity")
    duration_ms = (time.perf_counter() - started) * 1000.0
    average_equity = float(cast(float, equity_series.mean() or initial_capital))
    metrics: dict[str, float | int] = {
        "total_return": total_return(equity_series),
        "annualized_return": annualized_return(equity_series),
        "sharpe_ratio": sharpe_ratio(returns),
        "sortino_ratio": sortino_ratio(returns),
        "max_drawdown": max_drawdown(equity_series),
        "volatility": volatility(returns),
        "win_rate": win_rate(closed_trade_pnls),
        "number_of_trades": len(trades),
        "turnover": float(turnover_notional / average_equity) if average_equity else 0.0,
        "transaction_costs": total_transaction_costs,
        "slippage_costs": total_slippage_costs,
        "ending_portfolio_value": float(equity_series[-1]),
        "ending_equity": float(equity_series[-1]),
    }
    metadata = {
        "duration_ms": duration_ms,
        "candles_processed": prepared.height,
        "strategy_name": "moving_average_crossover",
        "dataset_size": prepared.height,
    }
    logger.info(
        "backtest completed",
        extra={
            "strategy_name": "moving_average_crossover",
            "candles_processed": prepared.height,
            "number_of_trades": len(trades),
            "duration_ms": duration_ms,
        },
    )
    return BacktestResult(
        equity_curve=equity_curve, trades=trades, metrics=metrics, metadata=metadata
    )
