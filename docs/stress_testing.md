# Stress testing and robustness

Mercury stress tests ask how a measured strategy result can fail. They are not
forecasts, confidence certificates, or a substitute for out-of-sample testing.

## Study contract

`POST /stress-tests` accepts an existing backtest experiment and stores an
auditable study in its `run_metadata`. Each result records the dataset and
strategy versions available on the experiment, engine version, circular block
bootstrap method, block size, simulation count, seed, input scenarios, and
explicit transformations. `GET /experiments/{id}/stress` retrieves it.

The initial scenarios are extra transaction costs, extra slippage, a one-bar
delayed fill with a stated penalty, and realised-volatility scaling. Cost and
delay shocks are applied on recorded trade timestamps; the volatility shock is
an explicit transformation of the realised return path. This is deliberately
not a market-microstructure simulator.

## Monte Carlo and limits

The engine uses a seeded circular block bootstrap. Blocks preserve some nearby
return dependence, unlike an IID shuffle. It reports median final return and
drawdown, a 5th-percentile drawdown, and simulated rates of negative terminal
return and Sharpe below zero. Those rates are conditional on the observed path
and bootstrap model; they are simulation-based estimates, never guarantees.

Trade-order reshuffling is intentionally not enabled: it is invalid when trade
outcomes are dependent. Historical stress periods must be supplied by available
dataset dates and regime labels; Mercury does not attach unsupported market
narratives to a date range.

## Explainable decisions

The robustness score preserves cost sensitivity, Monte Carlo outcomes,
drawdown distribution, and profit concentration as separate components. The
deterministic flags include `COST_SENSITIVITY_HIGH`,
`MONTE_CARLO_DRAWDOWN_HIGH`, `TAIL_RISK_HIGH`,
`PERFORMANCE_CONCENTRATION_HIGH`, and `SINGLE_PERIOD_DEPENDENCE`.

Campaigns can set `require_stress_testing: true` in constraints. The worker
then runs a small seeded validation stress study before ranking, persists the
components and flags, and incorporates its score into ranking. Larger studies
should be executed by the existing durable campaign-worker queue rather than
inside normal CI. Portfolio correlation stress is a transparent utility that
compares observed portfolio volatility with a correlation-one assumption.
