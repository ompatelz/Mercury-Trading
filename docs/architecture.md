# Mercury Architecture

Mercury is a modular monolith. The application deploys as one FastAPI service,
but the code is separated into API routes, services, repositories, models,
backtesting, research workflow, memory, and evals.

```text
Client
  -> FastAPI route
  -> Pydantic request schema
  -> Service module
  -> Repository / deterministic tool
  -> SQLAlchemy model
  -> PostgreSQL
```

The research workflow is intentionally linear today:

```text
memory retrieval
  -> hypothesis
  -> strategy specification
  -> backtest tool
  -> evaluation
  -> critic
  -> report
  -> lesson extraction
```

This keeps the first agent loop inspectable. Branching, retries, parallel
hypotheses, and human review can be introduced later if the workflow requires it.

Regime-aware research adds a deterministic layer between market data and
strategy evaluation:

```text
market bars
  -> no-lookahead regime labels
  -> backtest equity/trades
  -> per-regime performance
  -> regime robustness
  -> fitness / ranking / evolution
```

Strategy evolution is bounded by structured specifications. Mercury mutates and
selects validated strategy definitions; it does not store arbitrary generated
Python as the primary strategy representation.

Paper trading adds a live-style execution path without real broker integration:

```text
market bars
  -> historical replay stream
  -> registered strategy adapter
  -> signal event
  -> deterministic risk engine
  -> order event
  -> paper broker fill
  -> portfolio event
  -> trace persistence
```

Replay events are processed chronologically. The moving-average adapter makes a
decision for the current market event using only previously observed bars, then
the current bar is recorded for future events.

Live paper trading extends that same contract to streaming providers:

```text
live provider
  -> normalized live bar
  -> warmed strategy runner
  -> signal event
  -> deterministic risk engine
  -> paper broker fill
  -> portfolio event
  -> metrics / health / websocket update
```

Provider-specific formats stop at `LiveMarketDataProvider`. The execution path
still writes paper sessions, orders, fills, trace events, metrics, and portfolio
snapshots. No live broker implementation exists.

## Python and C++

Python remains the correctness reference. C++ acceleration is selective and must
match deterministic Python fixtures before it is trusted. The native module is
built by `scripts/build_native.py` locally and by CMake in CI.

## Persistence

PostgreSQL stores market bars, backtest experiments, trades, research
experiments, agent versions, workflow versions, memory lessons, trace events,
eval runs, task results, version comparisons, regime labels, evolution runs, and
strategy candidates. Paper-trading sessions persist orders, fills, trace events,
runtime metrics, and the latest or final portfolio snapshot.
# Campaign Architecture

```text
                    Mercury

             Research Campaign
                    |
             Research Planner
                    |
          +---------+---------+
          |                   |
      Memory             DB Job Queue
                              |
                         Worker Process
                              |
                      Strategy / Backtest
                              |
                         C++ Engine
                              |
                         Evaluation
                              |
               +--------------+--------------+
               |                             |
             Memory                       Ranking
                                               |
                                          Portfolio
                                               |
                                         Research Report
```

Campaign orchestration keeps the existing Mercury boundary: Python owns
orchestration, correctness, persistence, and agent control. C++ remains reserved
for benchmarked hot paths with parity tests.

New modules:

- `app/campaigns/service.py`: campaign planning, job submission, worker
  execution, finalization, ranking, portfolios, and reports.
- `app/campaigns/optimization.py`: grid, random, and deterministic
  Bayesian-like parameter search.
- `app/campaigns/splits.py`: temporal split validation.
- `app/campaigns/overfitting.py`: structured risk flags.
- `app/campaigns/ranking.py`: explainable candidate scoring.
- `app/campaigns/portfolio.py`: basic portfolio-level evaluation.
- `app/api/routes/campaigns.py`: thin HTTP layer.
- `scripts/run_worker.py`: background worker entrypoint.
