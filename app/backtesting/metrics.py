import math

import numpy as np
import polars as pl

TRADING_DAYS_PER_YEAR = 252


def total_return(equity: pl.Series) -> float:
    if len(equity) < 2:
        return 0.0
    return float(equity[-1] / equity[0] - 1.0)


def annualized_return(equity: pl.Series) -> float:
    if len(equity) < 2:
        return 0.0
    periods = len(equity) - 1
    gross_return = float(equity[-1] / equity[0])
    if gross_return <= 0:
        return -1.0
    return float(gross_return ** (TRADING_DAYS_PER_YEAR / periods) - 1.0)


def sharpe_ratio(returns: pl.Series) -> float:
    values = np.array(returns.fill_null(0.0).to_list(), dtype=float)
    if values.size < 2:
        return 0.0
    std = float(np.std(values, ddof=1))
    if math.isclose(std, 0.0):
        return 0.0
    return float(np.mean(values) / std * math.sqrt(TRADING_DAYS_PER_YEAR))


def sortino_ratio(returns: pl.Series) -> float:
    values = np.array(returns.fill_null(0.0).to_list(), dtype=float)
    downside = values[values < 0.0]
    if values.size < 2 or downside.size < 2:
        return 0.0
    downside_std = float(np.std(downside, ddof=1))
    if math.isclose(downside_std, 0.0):
        return 0.0
    return float(np.mean(values) / downside_std * math.sqrt(TRADING_DAYS_PER_YEAR))


def volatility(returns: pl.Series) -> float:
    values = np.array(returns.fill_null(0.0).to_list(), dtype=float)
    if values.size < 2:
        return 0.0
    return float(np.std(values, ddof=1) * math.sqrt(TRADING_DAYS_PER_YEAR))


def max_drawdown(equity: pl.Series) -> float:
    values = np.array(equity.to_list(), dtype=float)
    if values.size == 0:
        return 0.0
    running_max = np.maximum.accumulate(values)
    drawdowns = values / running_max - 1.0
    return float(drawdowns.min())


def win_rate(closed_trade_pnls: list[float]) -> float:
    if not closed_trade_pnls:
        return 0.0
    wins = sum(1 for pnl in closed_trade_pnls if pnl > 0)
    return float(wins / len(closed_trade_pnls))
