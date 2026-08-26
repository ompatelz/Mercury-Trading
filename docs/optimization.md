# Parameter Search and Trustworthy Optimization

Mercury optimization is a persisted study layer over a research campaign. It is
not a separate backtester and it does not let workers alter study state.

```text
Study coordinator -> durable campaign trial jobs -> workers -> backtests
       ^                                                       |
       +----------- persisted metrics, flags, and ranking ------+
```

## Parameter spaces

`ParameterSpace` accepts integer, float, categorical, and boolean parameters.
Legacy lists remain supported for existing campaigns. Numeric definitions can
use `min`, `max`, and `step`; categorical definitions use `values`; booleans
expand to `false` and `true`. Candidate hashes prevent repeated configurations.

Constraints are checked before a job is queued. The current moving-average
strategy always enforces `short_window < long_window`; extra constraints may use
`{"left": "a", "operator": "<", "right": "b"}`. Invalid candidates have
explicit rejection reasons rather than silently producing a backtest.

## Search and scoring

The supported methods are `grid`, seeded `random`, and `bayesian`. The Bayesian
proposal order uses Optuna TPE when the optional extra is installed; CI has a
deterministic diverse finite-space fallback. Install Optuna with:

```bash
pip install -e ".[dev,optimization]"
```

No search method is treated as an automatic winner. Persisted trial scoring uses
validation Sharpe and Sortino, drawdown, turnover, trade count, overfitting
flags, regime robustness, and walk-forward consistency. Each component is
returned from the trial API. Parameter sensitivity is reserved as an explicit
neighbouring-candidate measurement, rather than inventing a stability score.

## Validation discipline and pruning

Workers run train, validation, and walk-forward windows that end before the
locked test split. Only finalists selected by campaign ranking receive one test
evaluation. Trial records expose `test_set_used_for_optimization: false`.

Hard violations become `REJECTED`; worker failures become `FAILED`; cancellation
marks unfinished trials `PRUNED`. Pruning is deliberately conservative: Mercury
does not terminate candidates based on a noisy partial Sharpe estimate.

## API

```text
POST /optimization/studies
GET  /optimization/studies/{id}
GET  /optimization/studies/{id}/trials
POST /optimization/studies/{id}/run
POST /optimization/studies/{id}/cancel
```

A study creates one campaign and maps every candidate to both a durable
`campaign_experiment` and an `optimization_trial`. Existing campaign workers
lease and execute those backtests; the coordinator synchronizes measured results
into the study. Engine name and version come from the experiment's native/Python
backtest metadata.

## Reproducibility and throughput

Studies store the typed space, search method, seed, sampler metadata, dataset,
validation definition, trial order, engine metadata, and experiment IDs. Use
`scripts/benchmark_backtest.py` to measure native-engine throughput on the
target hardware before claiming an optimization-speed benefit; this change does
not fabricate a benchmark result.
