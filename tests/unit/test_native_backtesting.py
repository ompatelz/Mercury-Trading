from importlib import import_module
from typing import Any

import pytest

from app.backtesting.engine import run_moving_average_backtest
from app.backtesting.strategy import moving_average_crossover_signals
from tests.unit.test_backtesting import trend_bars


def test_native_execution_matches_python_reference() -> None:
    native = import_module("app.backtesting.native._engine")
    bars = trend_bars()
    prepared = moving_average_crossover_signals(bars, short_window=2, long_window=3)
    python_result = run_moving_average_backtest(
        bars=bars,
        short_window=2,
        long_window=3,
        initial_capital=10_000.0,
        transaction_cost_bps=1.0,
        slippage_bps=2.0,
    )

    native_result: dict[str, Any] = native.run_long_only_execution(
        prepared.get_column("timestamp").to_list(),
        prepared.get_column("open").to_list(),
        prepared.get_column("close").to_list(),
        prepared.get_column("position").to_list(),
        10_000.0,
        1.0,
        2.0,
    )

    native_equity = [row["equity"] for row in native_result["equity_curve"]]
    python_equity = python_result.equity_curve.get_column("equity").to_list()
    assert native_equity == pytest.approx(python_equity)

    assert len(native_result["trades"]) == len(python_result.trades)
    for native_trade, python_trade in zip(
        native_result["trades"], python_result.trades, strict=True
    ):
        assert native_trade["side"] == python_trade.side
        assert native_trade["quantity"] == pytest.approx(python_trade.quantity)
        assert native_trade["price"] == pytest.approx(python_trade.price)
        assert native_trade["notional"] == pytest.approx(python_trade.notional)
        assert native_trade["transaction_cost"] == pytest.approx(python_trade.transaction_cost)
        assert native_trade["slippage_cost"] == pytest.approx(python_trade.slippage_cost)
        assert native_trade["realized_pnl"] == pytest.approx(python_trade.realized_pnl)

    assert native_result["metrics"]["transaction_costs"] == pytest.approx(
        python_result.metrics["transaction_costs"]
    )
    assert native_result["metrics"]["slippage_costs"] == pytest.approx(
        python_result.metrics["slippage_costs"]
    )
    assert native_result["metrics"]["ending_portfolio_value"] == pytest.approx(
        python_result.metrics["ending_portfolio_value"]
    )
