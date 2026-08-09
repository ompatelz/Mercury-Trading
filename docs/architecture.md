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

## Python and C++

Python remains the correctness reference. C++ acceleration is selective and must
match deterministic Python fixtures before it is trusted. The native module is
built by `scripts/build_native.py` locally and by CMake in CI.

## Persistence

PostgreSQL stores market bars, backtest experiments, trades, research
experiments, agent versions, workflow versions, memory lessons, trace events,
eval runs, task results, and version comparisons.
