from importlib import import_module

import numpy as np
import pytest

from app.backtesting.backends import CppBacktestEngine, PythonBacktestEngine, get_backtest_engine
from tests.unit.test_backtesting import trend_bars


def _native_available() -> bool:
    native = import_module("app.backtesting.native._engine")
    try:
        native.run_long_only_execution(
            np.array([10.0]), np.array([10.0]), np.array([0.0]), 100.0, 0.0, 0.0
        )
    except TypeError:
        return False  # A stale local extension; CI always builds the checked-in source first.
    return True


@pytest.mark.skipif(not _native_available(), reason="native extension has not been rebuilt")
def test_native_execution_matches_python_reference() -> None:
    bars = trend_bars()
    python_result = PythonBacktestEngine().run_moving_average(bars, 2, 3, 10_000.0, 1.0, 2.0)
    native_result = CppBacktestEngine().run_moving_average(bars, 2, 3, 10_000.0, 1.0, 2.0)

    assert native_result.equity_curve.get_column("equity").to_list() == pytest.approx(
        python_result.equity_curve.get_column("equity").to_list()
    )
    assert native_result.metrics == pytest.approx(python_result.metrics)
    assert len(native_result.trades) == len(python_result.trades)
    for native_trade, python_trade in zip(native_result.trades, python_result.trades, strict=True):
        assert native_trade.quantity == pytest.approx(python_trade.quantity)
        assert native_trade.price == pytest.approx(python_trade.price)
        assert native_trade.realized_pnl == pytest.approx(python_trade.realized_pnl)
    assert native_result.metadata["input_layout"] == "contiguous"


@pytest.mark.skipif(not _native_available(), reason="native extension has not been rebuilt")
def test_native_rejects_invalid_prices_and_costs() -> None:
    native = import_module("app.backtesting.native._engine")
    with pytest.raises(ValueError, match="positive prices"):
        native.run_long_only_execution(
            np.array([10.0, np.nan]), np.array([10.0, 11.0]), np.zeros(2), 100.0, 0.0, 0.0
        )
    with pytest.raises(ValueError, match="non-negative"):
        native.run_long_only_execution(
            np.array([10.0]), np.array([10.0]), np.zeros(1), 100.0, -1.0, 0.0
        )


def test_engine_selection_is_explicit() -> None:
    assert get_backtest_engine("python").name == "python"
    assert get_backtest_engine("cpp").name == "cpp"
    with pytest.raises(ValueError, match="BACKTEST_ENGINE"):
        get_backtest_engine("gpu")
