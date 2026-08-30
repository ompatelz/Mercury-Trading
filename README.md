# Mercury

Mercury is an auditable quantitative-research system for testing structured strategy ideas against point-in-time market data. It combines a FastAPI and PostgreSQL application, deterministic Python-first research tooling, an optional C++ execution loop with parity tests, durable campaign workers, and a React observability dashboard.

It is deliberately **PAPER-only**. Mercury has no live-broker adapter and no code path that can place a real order.

## Why Mercury Exists

Research systems often retain a final metric but lose the decision trail: the hypothesis, available data, temporal split, costs, failed candidates, risk flags, and the reason a candidate was promoted or rejected. Mercury makes that trail a first-class artifact. Agentic components can propose or critique work, but deterministic services compute trading, validation, rankings, governance, and execution simulation.

## System Architecture

```text
                        React dashboard / CLI / API client
                                      |
                                  FastAPI routes
                                      |
        +-----------------------------+-----------------------------+
        |                             |                             |
  Research workflow              Campaign service            Dashboard queries
  memory -> hypothesis           plans -> durable jobs        metrics / lineage /
  -> strategy specification      -> PostgreSQL worker         paper-session state
        |                             |
        +--------------+--------------+
                       |
           deterministic research and validation
           backtests | temporal splits | regimes | walk-forward
           stress tests | rankings | portfolio evaluation
                       |
         artifacts / governance / reproducibility snapshots
                       |
                SHADOW simulation -> PAPER broker
                       |
                  PostgreSQL persisted state
```

Python owns correctness: data normalization, strategy validation, portfolio accounting, metrics, persistence, and orchestration. The native C++ path is optional and limited to the deterministic long-only execution loop; it is only trusted through Python/C++ parity tests.

## The Research Loop

1. Store and fingerprint normalized OHLCV bars.
2. Retrieve relevant lessons, define a bounded campaign, and create structured strategy candidates rather than arbitrary generated code.
3. Run experiments through durable PostgreSQL jobs with explicit budgets, retries, cancellation, runtime, and failure state.
4. Validate candidates with temporal train/validation/test separation, walk-forward summaries, regime metrics, costs, slippage, stress tests, and overfitting flags.
5. Rank candidates with explainable scores, evaluate basic portfolios, and persist reports, lineage, governance records, and reproduction metadata.
6. Run a selected candidate only in a shadow/PAPER simulation. Synthetic demo results are reproducibility evidence, not investment evidence.

## What Is Implemented

- Point-in-time backtesting with costs, slippage, trade and equity persistence.
- Structured strategy specifications, bounded evolution, lineage, and champion/challenger decisions.
- Regime-aware evaluation, no-lookahead labels, walk-forward checks, stress testing, optimization studies, overfitting flags, and portfolio evaluation.
- Agent/workflow evals, versioned promotion rules, research memory, and artifact-backed reproducibility checks.
- Durable campaign queue workers and an offline canonical end-to-end mission.
- Historical replay and monitored live-market-data **paper** sessions using a deterministic risk engine and paper broker.
- FastAPI endpoints plus a React/TypeScript dashboard for research, experiments, decisions, operations, lineage, and paper-session observability.

## Running Mercury

Requirements: Python 3.12+, PostgreSQL (or Docker), and pnpm for the dashboard.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Set a real local `POSTGRES_PASSWORD` in `.env`, then start the local stack:

```powershell
docker compose up --build
```

Compose runs migrations once before starting the API and worker, preventing a
startup migration race. The API is exposed at `http://localhost:8000`. In a
separate shell, start the dashboard:

```powershell
pnpm --dir frontend install
pnpm --dir frontend dev
```

For a source checkout without Docker, configure `DATABASE_URL`, run `alembic upgrade head`, start `uvicorn app.main:app --reload`, and run workers with `python scripts/run_worker.py --worker-name local-worker`.

### Developer checks

```powershell
mercury doctor --json
mercury demo
mercury demo --run
```

`mercury doctor` reports configuration and local capability without exposing a database secret or claiming a database connection is healthy. `mercury demo --run` executes the deterministic, offline PAPER-only mission.

## Testing and CI

```powershell
ruff check .
ruff format --check .
mypy app
python scripts/build_native.py
python -c "import app.backtesting.native._engine"
pytest
alembic heads
pnpm --dir frontend lint
pnpm --dir frontend typecheck
pnpm --dir frontend test
pnpm --dir frontend build
```

GitHub Actions validates Python quality and tests, clean PostgreSQL migrations, native build/import/parity, campaign-worker recovery, the canonical PAPER-only mission, frontend checks, dependency hygiene, Docker image construction, and a Compose API readiness smoke test. CI uses deterministic fixtures and does not need paid model calls or live market data.

## Measured Performance

Performance claims stay scoped to their capture. In the Stage 7 local Windows profile, `monte_carlo_bootstrap` on 10,000 returns and 100 simulations (three repeats) changed from median **841.8718 ms** to **16.8448 ms** after a deterministic NumPy implementation replaced the prior generator/Polars path. That is an approximately 50x machine-local result, not a production latency claim. See [performance methodology](docs/performance.md) for the command, measurement boundaries, and unmeasured surfaces.

## Project Structure

```text
app/                    FastAPI application and research services
  backtesting/          Python reference engine and native bridge
  campaigns/            planning, durable jobs, optimization, ranking
  dashboard/            query-oriented observability schemas/services
  evolution/            strategy specifications, fitness, lineage
  paper_trading/        replay/live paper runners, risk, broker, portfolio
  research_artifacts/   reports and reproducibility checks
  research_intelligence/ triage and governed research assistance
alembic/                database migrations
frontend/               React/TypeScript research dashboard
docs/                   architecture, operations, and methodology
tests/                  unit and integration coverage
```

## Documentation

Start with the [documentation index](docs/index.md), then read:

- [Architecture](docs/architecture.md) and [campaigns](docs/campaigns.md)
- [Data and point-in-time controls](docs/data.md), [regimes](docs/regimes.md), [walk-forward validation](docs/walk-forward.md), and [stress testing](docs/stress_testing.md)
- [Strategy lifecycle](docs/strategy_lifecycle.md), [evolution](docs/evolution.md), [ML research](docs/ml_research.md), and [research intelligence](docs/research_intelligence.md)
- [PAPER execution](docs/paper_trading.md), [production simulation](docs/production_simulation.md), [governance](docs/governance.md), and [security](docs/security.md)
- [Canonical demo](docs/canonical_demo.md), [testing](docs/testing.md), [performance](docs/performance.md), and [development](docs/development.md)

## Roadmap and Limits

Mercury is a research foundation, not a production trading system. Current limits include no real-money execution, no claim of production benchmark latency, and no distributed worker queue until PostgreSQL queue throughput demonstrates a need. External model providers remain behind deterministic eval gates; CI uses local deterministic behavior.

Planned UI refinement will use React Bits selectively for restrained metric and state transitions. Skiper UI patterns will be considered only with licensed access. The dashboard will remain data-dense, accessible, and focused on research decisions rather than decorative animation.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
