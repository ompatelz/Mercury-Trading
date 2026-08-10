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
  -> Walk-Forward Summary
  -> Overfitting Flags
  -> Strategy Ranking
  -> Portfolio Evaluation
  -> Campaign Report
```

Python owns correctness: market-data normalization, strategy validation,
portfolio accounting, metrics, eval scoring, and persistence. C++ is used only
where the Python reference has deterministic parity tests, currently the native
backtesting execution loop through pybind11.

## Current Capabilities

- Fetch, normalize, store, and query OHLCV bars.
- Run moving-average crossover backtests with costs and slippage.
- Persist experiments, metrics, trades, and research reports.
- Build and import the pybind11 native backtesting extension.
- Run a deterministic agentic research workflow without live LLM credentials.
- Track agent and workflow versions for research experiments.
- Extract structured lessons from completed research experiments.
- Classify simple market regimes from stored price data.
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
- Expose memory, eval, version, backtest, market-data, and research APIs.

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

Worker:

```bash
python scripts/run_worker.py --worker-name local-worker
```

Docker:

```bash
docker compose up --build
docker compose down
```

Docker Compose starts PostgreSQL, the API, and a campaign worker.

## Running Tests

```bash
ruff check .
ruff format --check .
mypy app
python scripts/build_native.py
python -c "import app.backtesting.native._engine"
pytest
alembic heads
docker build .
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
```

## Project Structure

```text
app/
  api/routes/        HTTP endpoints
  agents/            agent and workflow version services
  backtesting/       strategy execution, metrics, native bridge
  evals/             deterministic benchmark and promotion framework
  experiments/       backtest persistence service
  market_data/       providers, normalization, repository
  memory/            regime classification, embeddings, lesson retrieval
  campaigns/         campaign planning, persisted jobs, optimization, ranking
  models/            SQLAlchemy database models
  research/          agent workflow and research experiment service
alembic/             database migrations
tests/               unit and integration tests
docs/                architecture and development notes
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
- Realistic transaction costs and slippage in backtests.
- Measurable agent improvement through evals and promotion rules.
- Structured memory, not raw model transcript storage.
- CI-safe deterministic tests before live model integrations.
- Campaign autonomy is budgeted and finite; no infinite research loops.
- The final test split is locked during optimization to reduce leakage.

## Roadmap

- [x] Backend foundation
- [x] Market data and backtesting engine
- [x] Native execution parity path
- [x] Agentic research workflow
- [x] Memory, evals, and controlled promotion rules
- [x] Research campaigns, persisted jobs, optimization, walk-forward summaries,
      overfitting flags, ranking, and portfolio evaluation
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
- [Testing](docs/testing.md)
