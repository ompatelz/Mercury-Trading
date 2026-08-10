# Strategy Specification

Mercury represents strategies as structured data. The current interpreter
supports `moving_average_crossover`, but the schema is designed to grow without
storing arbitrary executable model-generated code.

Important fields:

- `strategy_family`: engine-compatible strategy family.
- `signal_type`: broad signal behavior such as trend following.
- `lookback`: primary lookback length.
- `entry_conditions`: validated signal parameters.
- `exit_conditions`: deterministic exit rules.
- `position_sizing`: fixed or volatility-targeted sizing configuration.
- `volatility_filter` and `trend_filter`: optional bounded filters.
- `risk_parameters`: drawdown or exposure limits.
- `execution_parameters`: costs and slippage assumptions.

The specification is also the unit of mutation and lineage. Every generated
candidate records parent IDs, changed fields, generation, memory influence, and
promotion status.
