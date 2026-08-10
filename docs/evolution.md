# Strategy Evolution

Mercury's evolutionary search is metric-driven. LLMs may later suggest mutation
ideas behind typed contracts, but selection and promotion remain deterministic.

```text
Initial population
  -> Backtest
  -> Regime evaluation
  -> Fitness
  -> Selection
  -> Mutation / compatible crossover
  -> Next generation
```

Mutation changes bounded strategy dimensions such as lookback, volatility
filters, position sizing, exit logic, and risk parameters. Crossover is allowed
only for compatible strategy families and signal types.

Population diversity is tracked through parameter distance and strategy-family
coverage. This reduces collapse where every candidate becomes the same parameter
variant.

Champion/challenger promotion requires a meaningful fitness improvement and no
blocking regime or overfitting flags. A single better backtest is not enough.

Campaigns can request bounded evolution through constraints. The campaign
service remains the state-machine owner and records any generated evolution run
in the campaign report.
