# Market Regimes

Mercury's regime engine is deterministic. It does not ask a model whether the
market is bullish, volatile, or mean-reverting.

For each bar, the engine computes a rolling window using only current and prior
bars. The current version records rolling return, moving-average slope,
realized volatility, ATR ratio, drawdown, autocorrelation, and trend strength.

Labels are versioned as `regime-v1` and persisted per symbol, interval,
timestamp, and version. This keeps historical experiments reproducible when the
classification logic changes later.

```text
MarketBar history through t
  -> rolling features
  -> trend label
  -> volatility label
  -> character label
  -> composite regime
```

Leakage protection is mandatory: changing a future price must not alter earlier
regime labels. Tests prove this directly with synthetic data.

Regime transitions measure when the composite label changes, how long the prior
regime lasted, and when the transition occurred. Mercury uses this for research
diagnostics only; live strategy switching is intentionally excluded.
