# Mercury

Mercury is an autonomous quant research platform for running reproducible market
experiments and learning from the results. It combines a FastAPI/PostgreSQL
backend, deterministic Python-first backtesting, selective C++ acceleration, and a
controlled agent workflow that records hypotheses, strategies, metrics, critiques,
research lessons, and eval outcomes.

## Why Mercury Exists

Quant research produces many repeated experiments. Most systems preserve metrics
but lose the reasoning: why a strategy failed, which regime it failed in, whether
an agent missed a risk rule, and whether a workflow change actually improved
research quality.

Mercury treats research as an auditable loop. Agents can propose and critique
experiments, but deterministic tools calculate trades, metrics, regimes, eval
scores, campaign rankings, and promotion decisions. Persisted research campaigns
let Mercury explore batches of strategy variants without turning into an
uncontrolled agent swarm.

## Architecture

```text
Market Data
  -> Normalization / Storage
  -> Memory Retrieval
  -> Hypothesis Agent
  -> Strategy Specification
  -> Strategy Registry
  -> Backtesting Engine
  -> Risk / Evaluation
  -> Critic
  -> Lesson Extractor
  -> Research Memory

Agent / Workflow Version
  -> Benchmark Eval
  -> Candidate Config
  -> Benchmark Eval
  -> Compare
  -> Promote or Reject

Research Campaign
  -> Temporal Split
  -> Parameter Search
  -> Persisted Job Queue
  -> Worker
  -> Train / Validation Backtests
  -> Regime Evaluation
  -> Walk-Forward Summary
  -> Overfitting Flags
  -> Strategy Ranking
  -> Strategy Evolution
  -> Champion / Challenger
  -> Portfolio Evaluation
  -> Campaign Report

Paper Trading Replay
  -> Historical Market Event Stream
  -> Strategy Signal
  -> Risk Checks
  -> Market Order
  -> Paper Broker Fill
  -> Portfolio Snapshot
  -> Trace Events

Live Paper Trading
  -> Live Market Feed
  -> Normalized Market Events
  -> Warmed Strategy Runner
  -> Signals
  -> Risk Checks
  -> Paper Broker Fill
  -> Portfolio / Monitoring / WebSocket Updates
```

Python owns correctness: market-data normalization, strategy validation,
portfolio accounting, metrics, eval scoring, and persistence. C++ is used only
where the Python reference has deterministic parity tests, currently the native
backtesting execution loop through pybind11.

## Current Capabilities

- Fetch, normalize, store, and query OHLCV bars.
- Run moving-average crossover backtests with costs and slippage.
- Persist experiments, metrics, trades, reproducibility snapshots, and research
  artifacts.
- Build and import the pybind11 native backtesting extension.
- Run a deterministic agentic research workflow without live LLM credentials.
- Track agent and workflow versions for research experiments.
- Extract structured lessons from completed research experiments.
- Classify deterministic market regimes from stored price data without
  look-ahead.
- Persist timestamped regime features, labels, transitions, and version
  metadata.
- Evaluate strategy performance by regime and calculate regime robustness.
- Retrieve relevant lessons before new research runs.
- Run deterministic agent eval benchmarks and store task results.
- Compare baseline and candidate workflow versions with promotion rules.
- Create research campaigns with objectives, constraints, universes, budgets,
  temporal splits, hypotheses, planned variants, and final conclusions.
- Queue campaign experiments as persisted background jobs with attempts,
  runtime, retry, failure, and cancellation state.
- Run grid, random, and deterministic Bayesian-like parameter exploration.
- Enforce train/validation/test split definitions and keep the test period locked
  during parameter exploration.
- Aggregate walk-forward robustness summaries.
- Generate explicit overfitting/risk flags.
- Rank candidate strategies with explainable component scores.
- Evaluate basic equal-weight, volatility-adjusted, and simple risk-parity
  portfolios across top candidates.
- Represent strategies as structured specifications rather than arbitrary
  generated code.
- Run bounded evolutionary strategy search with selection, mutation, lineage,
  diversity metrics, and champion/challenger decisions.
- Compare memory-conditioned evolution with memory-off evolution.
- Replay stored historical bars through a simulated paper-trading execution
  loop.
- Persist paper sessions, orders, fills, trace events, and final portfolio
  snapshots.
- Consume normalized live market bars through a provider abstraction.
- Run bounded or continuous live paper-trading sessions with historical warm-up,
  lifecycle state, reconnect attempts, market-session awareness, latency
  metrics, and component health.
- Expose live session commands, metrics, portfolio state, orders, and
  WebSocket updates under `/live`.
- Expose a research dashboard API and React dashboard for experiments,
  reproducible reports, campaigns, regime performance, strategy lineage, and
  paper-trading monitors.
- Export experiment and campaign reports as structured JSON or Markdown, with
  measured results separated from interpretation.
- Reproduce stored experiments from captured configuration and current market
  data fingerprints, then compare metrics with explicit tolerances.
- Enforce explicit `PAPER` execution mode; real-money trading is not
  implemented.
- Expose memory, eval, version, backtest, market-data, and research APIs.

## Research Dashboard

Mercury includes a Vite React/TypeScript dashboard under `frontend/`. It is an
observability interface for the research loop rather than a trading terminal:

```text
Research Campaign
  -> Hypotheses
  -> Strategies
  -> Backtests
  -> Evaluation
  -> Evolution
  -> Champion / Challenger
```

The dashboard reads query-oriented backend endpoints under `/dashboard`:

- `GET /dashboard/overview`
- `GET /dashboard/experiments`
- `GET /dashboard/experiments/{experiment_id}`
- `GET /dashboard/campaigns/{campaign_id}`
- `GET /dashboard/strategies/{strategy_id}/lineage`
- `GET /dashboard/strategies/compare`
- `GET /dashboard/paper-trading/sessions/{session_id}`
- `GET /experiments/{experiment_id}/report`
- `POST /experiments/{experiment_id}/reproduce`

These endpoints aggregate persisted Mercury state from experiments, campaign
jobs, strategy candidates, memory lessons, and paper-trading sessions. The
frontend does not duplicate promotion, regime, report-generation, or risk logic;
it renders the metrics and explanations already persisted by the backend.

## Regime-Aware Research

Mercury labels market regimes from quantitative features available at each bar:
rolling return, moving-average slope, realized volatility, ATR ratio, drawdown,
trend strength, and autocorrelation. A label at timestamp `t` only uses data at
or before `t`; future bars cannot change prior labels.

The first regime version classifies:

```text
trend: bullish | bearish | sideways
volatility: low | normal | high
character: trending | mean_reverting
```

Backtests store per-regime return, Sharpe, Sortino, drawdown, win rate,
turnover, and trade count. The regime robustness score penalizes weak worst-case
regimes, high dispersion, insufficient regime coverage, high drawdown, and thin
trade support.

## Strategy Evolution

Strategies are represented as structured `StrategySpecification` objects:

```text
strategy_family
signal_type
lookback
entry_conditions
exit_conditions
position_sizing
volatility_filter
trend_filter
risk_parameters
execution_parameters
```

Evolution is deterministic and metric-driven:

```text
population
  -> evaluate
  -> score fitness
  -> select
  -> mutate compatible specifications
  -> preserve lineage
  -> compare champion/challenger
```

Fitness is multi-component. It includes out-of-sample risk-adjusted return,
Sortino, drawdown control, walk-forward consistency, regime robustness,
turnover, trade count, overfitting flags, and a simple complexity penalty.
Mercury prefers simpler strategies with similar robust performance.

## Paper Trading

Mercury supports simulated paper execution over stored historical bars. The
paper engine replays market bars chronologically, lets the registered strategy
emit structured signals from prior bars only, applies deterministic risk checks,
fills market orders through a `PaperBroker`, and updates portfolio state only
from fill events.

The first broker is intentionally paper-only. There is no live broker adapter and
no code path that can submit real orders.

## Live Paper Trading

Mercury can run the same paper-only strategy/risk/broker/portfolio pipeline from
a live market-data provider. The first real adapter polls Yahoo Finance for
recent intraday bars and normalizes them before execution. Tests and CI use a
static fake live feed and never depend on an external market-data API.

Live sessions support optional historical warm-up from stored bars before the
stream starts. Runtime state tracks feed lifecycle, latest market event, signal,
order, portfolio snapshot, PnL, drawdown, rejected orders, processing latency,
errors, and component health. Real-money execution remains unavailable.

## Memory-Guided Search

Evolution can retrieve prior research lessons before mutation. A candidate
records which memories were retrieved, whether they influenced mutation, and
whether the resulting candidate improved fitness. Mercury also exposes a
memory-on versus memory-off comparison runner so memory value is measured rather
than assumed.

## Validation

Mercury validates research quality through no-lookahead regime tests,
train/validation/test separation, walk-forward checks, overfitting flags,
transaction costs, slippage, native Python/C++ parity, migration checks, worker
tests, and Docker builds. Live regime switching is deliberately out of scope for
the research foundation.

## Self-Improvement

Mercury does not let an agent rewrite arbitrary source code. Improvements are
represented as versioned configuration or workflow artifacts, then tested against
a fixed benchmark.

```text
baseline workflow
  -> benchmark
  -> candidate workflow
  -> same benchmark
  -> metric comparison
  -> promote/reject decision
```

Promotion currently considers task success, invalid-strategy rejection, and
latency thresholds. The decision and metric differences are stored in
`version_comparisons`.

## Tech Stack

- Backend: FastAPI, Pydantic, SQLAlchemy.
- Quant engine: Polars, NumPy, Python reference backtester.
- Native acceleration: C++, CMake, pybind11.
- Data: PostgreSQL, Alembic migrations, JSON structured metadata.
- Agents: deterministic local model boundary for CI-safe research workflows.
- Memory and evals: structured lessons, deterministic embeddings, benchmark
  tasks, promotion rules.
- Campaigns: persisted PostgreSQL job queue, deterministic campaign
  orchestration, temporal splits, ranking, portfolio evaluation.
- Quality: pytest, Ruff, mypy, GitHub Actions, Docker.

## Running Mercury

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

The API runs at `http://localhost:8000`.

Workers use durable PostgreSQL leases and can run independently:

```bash
python scripts/run_worker.py --worker-name research-a
python scripts/run_worker.py --worker-name research-b
```

See [worker architecture and operations](docs/workers.md) for idempotency,
retries, cancellation, recovery, and benchmark instructions.

Docker:

```bash
docker compose up --build
docker compose down
```

Docker Compose starts PostgreSQL, the API, and a campaign worker.

Dashboard:

```bash
pnpm --dir frontend install
pnpm --dir frontend dev
```

The Vite dev server proxies `/dashboard` to `http://127.0.0.1:8000`. If the API
runs elsewhere, set `VITE_API_BASE_URL` before starting the frontend.

## Running Tests

```bash
ruff check .
ruff format --check .
mypy app
python scripts/build_native.py
python -c "import app.backtesting.native._engine"
pytest
pytest tests/unit/test_paper_trading.py tests/integration/test_api.py
alembic heads
docker build .
pnpm --dir frontend lint
pnpm --dir frontend typecheck
pnpm --dir frontend test
pnpm --dir frontend build
pnpm --dir frontend exec playwright install chromium
pnpm --dir frontend e2e
```

Migrations need a reachable PostgreSQL database matching `DATABASE_URL`. The
default local URL expects user `mercury`, password `mercury`, and database
`mercury`.

## API Examples

```bash
curl http://localhost:8000/health

curl -X POST http://localhost:8000/research/experiments \
  -H "Content-Type: application/json" \
  -d '{"objective":"Explore trend-following behavior on MSFT","symbol":"MSFT","start_date":"2024-01-01","end_date":"2024-06-01","interval":"1d"}'

curl -X POST http://localhost:8000/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query":"MSFT moving average high volatility failure","symbol":"MSFT","top_k":3}'

curl -X POST http://localhost:8000/evals/run \
  -H "Content-Type: application/json" \
  -d '{"benchmark_name":"research_agent_v1"}'

curl -X POST http://localhost:8000/campaigns \
  -H "Content-Type: application/json" \
  -d '{"objective":"Can medium-term momentum produce robust returns on MSFT?","symbols":["MSFT"],"start_date":"2024-01-01","end_date":"2024-06-01","budget":{"max_experiments":4,"max_optimization_trials":4},"parameter_space":{"short_window":[5,10],"long_window":[20,50]},"optimization_method":"grid"}'

curl -X POST http://localhost:8000/campaigns/{campaign_id}/run \
  -H "Content-Type: application/json" \
  -d '{"batch_size":4}'

python scripts/run_worker.py --max-jobs 4 --worker-name local-worker

curl http://localhost:8000/campaigns/{campaign_id}/rankings
curl http://localhost:8000/campaigns/{campaign_id}/portfolios
curl http://localhost:8000/campaigns/{campaign_id}/report

curl http://localhost:8000/experiments/{experiment_id}/report
curl http://localhost:8000/experiments/{experiment_id}/report?format=markdown
curl -X POST http://localhost:8000/experiments/{experiment_id}/reproduce
python scripts/reproduce_experiment.py {experiment_id}

curl -X POST http://localhost:8000/regimes \
  -H "Content-Type: application/json" \
  -d '{"symbol":"MSFT","start":"2024-01-01","end":"2024-06-01","lookback":20}'

curl http://localhost:8000/strategies/{backtest_id}/regime-performance

curl -X POST http://localhost:8000/evolution-runs \
  -H "Content-Type: application/json" \
  -d '{"objective":"Evolve robust moving-average variants for MSFT","symbol":"MSFT","start":"2024-01-01","end":"2024-06-01","generations":2,"population_size":3}'

curl -X POST http://localhost:8000/paper-trading/sessions \
  -H "Content-Type: application/json" \
  -d '{"symbol":"MSFT","start":"2024-01-01","end":"2024-06-01","strategy_parameters":{"fast_window":5,"slow_window":20},"execution_mode":"PAPER","initial_cash":10000}'

curl http://localhost:8000/paper-trading/sessions/{session_id}/orders
curl http://localhost:8000/paper-trading/sessions/{session_id}/trades
curl http://localhost:8000/paper-trading/sessions/{session_id}/portfolio

curl -X POST http://localhost:8000/live/sessions \
  -H "Content-Type: application/json" \
  -d '{"symbol":"MSFT","interval":"1m","strategy_parameters":{"fast_window":5,"slow_window":20},"execution_mode":"PAPER","warmup_start":"2024-01-01","warmup_end":"2024-02-01","initial_cash":10000}'

curl http://localhost:8000/live/sessions/{session_id}
curl http://localhost:8000/live/sessions/{session_id}/metrics
curl http://localhost:8000/live/sessions/{session_id}/portfolio
curl http://localhost:8000/live/sessions/{session_id}/orders
curl -X POST http://localhost:8000/live/sessions/{session_id}/stop
```

## Project Structure

```text
app/
  api/routes/        HTTP endpoints
  agents/            agent and workflow version services
  backtesting/       strategy execution, metrics, native bridge
  dashboard/         dashboard aggregation and observability schemas
  evals/             deterministic benchmark and promotion framework
  experiments/       backtest persistence service
  market_data/       providers, normalization, repository
  memory/            regime classification, embeddings, lesson retrieval
  paper_trading/     replay/live runners, risk, paper broker, portfolio, monitoring
  regimes/           deterministic regime engine and per-regime metrics
  evolution/         strategy specs, mutation, fitness, lineage
  campaigns/         campaign planning, persisted jobs, optimization, ranking
  research_artifacts/ structured report generation and reproduction checks
  models/            SQLAlchemy database models
  research/          agent workflow and research experiment service
alembic/             database migrations
tests/               unit and integration tests
docs/                architecture and development notes
frontend/            React/TypeScript research dashboard
```

## Example Research Run

With deterministic bars already stored:

```text
objective: Explore trend-following behavior on MSFT
hypothesis: MSFT may exhibit short-term trend persistence
strategy: moving_average_crossover
backtest: costs, slippage, trades, equity, Sharpe, drawdown
critic: identifies missing robustness and out-of-sample checks
memory: stores a lesson tagged by strategy, symbol, regime, and failure reasons
eval: benchmark tasks score workflow behavior without live API calls
```

## Engineering Principles

- Reproducible experiments and explicit version metadata.
- No-lookahead strategy execution.
- No-lookahead regime detection.
- Realistic transaction costs and slippage in backtests.
- Measurable agent improvement through evals and promotion rules.
- Structured memory, not raw model transcript storage.
- CI-safe deterministic tests before live model integrations.
- Campaign autonomy is budgeted and finite; no infinite research loops.
- The final test split is locked during optimization to reduce leakage.
- Strategies evolve through structured specifications, not arbitrary generated
  Python.
- Paper trading is simulated execution only; real broker adapters are out of
  scope until the paper path is validated.

## Roadmap

- [x] Backend foundation
- [x] Market data and backtesting engine
- [x] Native execution parity path
- [x] Agentic research workflow
- [x] Memory, evals, and controlled promotion rules
- [x] Research campaigns, persisted jobs, optimization, walk-forward summaries,
      overfitting flags, ranking, and portfolio evaluation
- [x] Regime-aware evaluation and bounded strategy evolution
- [x] Simulated paper-trading replay and event-driven execution
- [x] Live market-data ingestion and monitored live paper trading
- [ ] pgvector-backed semantic search
- [ ] Distributed Redis/Celery workers when DB queue throughput is insufficient
- [ ] Live model provider integration behind deterministic eval gates

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Technical Docs

- [Architecture](docs/architecture.md)
- [Campaigns](docs/campaigns.md)
- [Workers](docs/workers.md)
- [Optimization](docs/optimization.md)
- [Walk-forward analysis](docs/walk-forward.md)
- [Portfolio evaluation](docs/portfolio.md)
- [Regime-aware research](docs/regimes.md)
- [Strategy specifications](docs/strategy-specification.md)
- [Evolution](docs/evolution.md)
- [Research artifacts](docs/research_artifacts.md)
- [Fitness](docs/fitness.md)
- [Testing](docs/testing.md)
- [Paper trading](docs/paper_trading.md)
- [Live execution](docs/live_execution.md)
- [Performance and native backtesting](docs/performance.md)
