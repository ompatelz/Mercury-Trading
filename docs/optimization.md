# Parameter Search and Optimization

Mercury supports three campaign parameter exploration methods:

- `grid`: exhaustive combinations for small controlled spaces.
- `random`: deterministic seeded sampling for broader spaces.
- `bayesian`: Optuna TPE search when the optional `optimization` extra is
  installed; otherwise a deterministic center-biased fallback for CI.

The Bayesian path is optional so normal CI does not need extra optimization
packages. Install it with:

```bash
pip install -e ".[dev,optimization]"
```

It should not optimize only for Sharpe; it must include drawdown, turnover,
trade count, validation behavior, and out-of-sample robustness.

Current scoring considers:

- Sharpe
- Sortino
- max drawdown
- turnover
- trade count
- overfitting flags

The implementation lives in `app/campaigns/optimization.py` and
`app/campaigns/ranking.py`.
