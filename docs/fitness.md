# Fitness and Robustness

Mercury does not optimize purely for Sharpe. Fitness is a transparent composite
score built from:

- out-of-sample Sharpe
- Sortino
- max drawdown
- walk-forward consistency
- regime robustness
- turnover
- trade count
- strategy complexity
- overfitting and risk flags

Regime robustness is not an average Sharpe. It considers regime coverage,
worst-regime performance, dispersion between regimes, drawdown, and minimum
trade support.

The complexity penalty is intentionally simple. It counts conditions,
parameters, indicators, and filters. Mercury should prefer a simpler strategy
with comparable robust performance over a more complicated candidate with a
slightly better backtest.
