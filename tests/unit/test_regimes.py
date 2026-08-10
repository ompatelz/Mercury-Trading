from datetime import datetime, timedelta
from decimal import Decimal

import polars as pl
from sqlalchemy.orm import Session

from app.backtesting.engine import run_moving_average_backtest
from app.models.market_data import MarketBar
from app.regimes.engine import classify_regimes, summarize_transitions
from app.regimes.performance import performance_by_regime, regime_robustness_score
from app.regimes.service import RegimeService


def test_regime_classification_is_deterministic_and_detects_synthetic_regimes() -> None:
    bars = _bars([100 + index for index in range(30)] + [130 - index * 2 for index in range(30)])

    first = classify_regimes(bars, lookback=10)
    second = classify_regimes(bars, lookback=10)

    assert [item.composite_regime for item in first] == [item.composite_regime for item in second]
    assert any(item.trend_regime == "bullish" for item in first)
    assert any(item.trend_regime == "bearish" for item in first)
    assert summarize_transitions(first)


def test_regime_labels_do_not_use_future_prices() -> None:
    bars = _bars([100 + index for index in range(50)])
    shocked_future = list(bars)
    shocked_future[-1] = _bar(index=49, close=10_000)

    original = classify_regimes(bars, lookback=12)
    shocked = classify_regimes(shocked_future, lookback=12)

    assert [item.features for item in original[:40]] == [item.features for item in shocked[:40]]
    assert [item.composite_regime for item in original[:40]] == [
        item.composite_regime for item in shocked[:40]
    ]


def test_regime_service_persists_versioned_labels(db_session: Session) -> None:
    db_session.add_all(_bars([100 + index for index in range(15)]))
    db_session.flush()

    labels = RegimeService(db_session).compute_and_persist("MSFT", lookback=5)

    assert labels
    assert labels[0].regime_version == "regime-v1"
    assert labels[0].features["lookback"] == 5


def test_per_regime_performance_and_robustness_are_explainable() -> None:
    bars = _bars([100 + index for index in range(40)])
    frame = pl.DataFrame(
        [
            {
                "timestamp": bar.timestamp,
                "open": float(bar.open),
                "high": float(bar.high),
                "low": float(bar.low),
                "close": float(bar.close),
                "volume": bar.volume,
            }
            for bar in bars
        ]
    )
    backtest = run_moving_average_backtest(
        frame,
        short_window=3,
        long_window=8,
        initial_capital=10_000,
        transaction_cost_bps=1,
    )
    labels = classify_regimes(bars, lookback=8)

    metrics = performance_by_regime(backtest.equity_curve, labels)
    score, flags, components = regime_robustness_score(metrics)

    assert metrics
    assert score >= 0.0
    assert "coverage" in components
    assert isinstance(flags, list)


def _bars(closes: list[float]) -> list[MarketBar]:
    return [_bar(index=index, close=close) for index, close in enumerate(closes)]


def _bar(index: int, close: float) -> MarketBar:
    timestamp = datetime(2024, 1, 1) + timedelta(days=index)
    return MarketBar(
        symbol="MSFT",
        timestamp=timestamp,
        interval="1d",
        open=Decimal(str(close)),
        high=Decimal(str(close + 1)),
        low=Decimal(str(close - 1)),
        close=Decimal(str(close)),
        volume=1_000 + index,
    )
