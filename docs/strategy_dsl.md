# Strategy DSL and controlled execution

Mercury accepts strategy **data**, never generated Python or dataframe expressions. DSL v1 is deliberately small: SMA indicators, named indicator comparisons, `all`/`any` logical combinations, percentage-of-equity sizing, bounded filters, and explicit runtime limits.

`POST /strategies/validate` parses and semantically validates a proposal. `POST /strategies` stores an accepted immutable record, while `GET /strategies/{id}` and `/explain` expose its structured rules and deterministic explanation.

The compiler canonicalizes JSON (sorted keys, compact encoding), hashes it with SHA-256, calculates complexity, and emits a readable execution plan. Persisted records include DSL and compiler versions, validation state, complexity, explanation, and hash. The current engine version remains in experiment metadata.

No-lookahead is structural: conditions may name only declared indicators and indicators can only be rolling SMA values of `close`. The interpreter evaluates a completed bar and shifts each position one bar before execution, so a signal may trade only at the next open. There is no syntax for `t + 1`, arbitrary columns, Python code, filesystem access, environment variables, or network access.

The normal runtime does not execute plugins or custom source, so a subprocess sandbox is not a substitute for validation and is intentionally not used. Resource limits reject excessive bars, indicators, and rule complexity before evaluation. `max_runtime_ms` is recorded as a contract for the runtime boundary; the existing Python/C++ execution loops retain their own deterministic backtest bounds.

Existing research output remains compatible through a one-way adapter: the registered `moving_average_crossover` with `fast_window` and `slow_window` becomes the DSL's `fast_ma` and `slow_ma` spec before the legacy backtest request is issued. Evolution already mutates structured window fields; optimization consumes the same bounded parameters. Future C++ work should consume the compiler's execution plan, with Python remaining the parity oracle.
