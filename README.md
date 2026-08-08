# Mercury

Mercury is a self-improving autonomous quant research platform. Phase 1 is deliberately small: it builds the backend foundation that later research agents, memory systems, and orchestration can depend on.

## What Phase 1 Supports

- Fetch historical OHLCV bars through a provider interface.
- Normalize and validate market data before persistence.
- Store bars and experiment records in PostgreSQL.
- Expose a typed FastAPI REST API.
- Run one baseline moving-average crossover backtest.
- Persist reproducible experiment metadata and metrics.
- Run locally with Docker Compose.
- Run CI checks with GitHub Actions.

## Architecture

Mercury Phase 1 is a modular monolith. A modular monolith keeps one deployable application while separating HTTP, market-data, backtesting, experiment, and persistence concerns. That is the right tradeoff before the platform has enough complexity to justify services, queues, or distributed infrastructure.

```mermaid
flowchart TD
    Client["Client or researcher"] --> API["FastAPI routes"]
    API --> Schemas["Pydantic schemas"]
    API --> Services["Service layer"]
    Services --> Provider["MarketDataProvider interface"]
    Provider --> Yahoo["Yahoo Finance provider"]
    Services --> Normalize["Polars normalization and validation"]
    Normalize --> DB["PostgreSQL via SQLAlchemy"]
    Services --> Backtester["Moving-average backtester"]
    Backtester --> Metrics["Return, Sharpe, drawdown, trades"]
    Metrics --> Experiments["Experiment record"]
    Experiments --> DB
```

### Request Flow

```text
API request
  -> Pydantic request validation
  -> thin FastAPI route
  -> service layer
  -> provider, repository, or backtester
  -> SQLAlchemy session
  -> PostgreSQL
  -> typed response schema
```

## Technology Choices

- FastAPI provides the REST API layer, request validation hooks, and OpenAPI documentation.
- Pydantic schemas define explicit request and response contracts instead of returning raw ORM objects.
- SQLAlchemy ORM maps Python objects to database rows while keeping persistence details out of business logic.
- Alembic manages database migrations; production startup should not rely on `Base.metadata.create_all()`.
- PostgreSQL is durable, familiar, and supports JSONB experiment metadata.
- Polars is used for market-data normalization and backtest table calculations.
- NumPy supports metric calculations such as Sharpe ratio and max drawdown.
- Docker images package the application; Docker containers are running instances of those images.
- Docker Compose starts the API and PostgreSQL together for local development.
- GitHub Actions runs CI checks on pushes and pull requests.

## What We Are Not Adding Yet

Phase 1 intentionally excludes LLM agents, LangGraph, Redis, embeddings, RAG, Kafka, Kubernetes, TimescaleDB, and microservices. Those tools may become useful later, but adding them before the data, backtest, and experiment foundation is stable would create operational complexity without improving the core research workflow.

## Local Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
```

For Docker:

```bash
docker compose up --build
```

The API will be available at `http://localhost:8000`.

## Environment Configuration

`DATABASE_URL` controls the database connection.

Local host example:

```bash
DATABASE_URL=postgresql+psycopg://mercury:mercury@localhost:5432/mercury
```

Docker Compose example:

```bash
DATABASE_URL=postgresql+psycopg://mercury:mercury@db:5432/mercury
```

## Database Migrations

Database migrations are versioned schema changes. Mercury uses Alembic so schema changes are explicit, reviewable, and repeatable.

```bash
alembic upgrade head
```

## Developer Commands

```bash
ruff check .
ruff format .
ruff format --check .
mypy app
pytest
alembic upgrade head
uvicorn app.main:app --reload
docker compose up --build
```

## API Examples

Health:

```bash
curl http://localhost:8000/health
```

Ingest market data:

```bash
curl -X POST http://localhost:8000/market-data/ingest \
  -H "Content-Type: application/json" \
  -d '{"symbol":"MSFT","start":"2024-01-01","end":"2024-06-01","interval":"1d"}'
```

List stored bars:

```bash
curl "http://localhost:8000/market-data/MSFT?start=2024-01-01&end=2024-06-01&interval=1d"
```

Run a backtest:

```bash
curl -X POST http://localhost:8000/backtests \
  -H "Content-Type: application/json" \
  -d '{"symbol":"MSFT","start":"2024-01-01","end":"2024-06-01","interval":"1d","short_window":20,"long_window":50,"initial_capital":10000,"transaction_cost_bps":1}'
```

## Backtesting Notes

The baseline strategy is moving-average crossover:

- Calculate short and long moving averages from close prices.
- Target long exposure when short MA is above long MA.
- Shift the signal by one bar before applying returns.
- Charge transaction costs whenever the position changes.

The signal shift is how the implementation avoids look-ahead bias: today’s return is multiplied by the position known before today’s return is realized, not by a signal computed after seeing the close.

Transaction costs model the friction paid when changing exposure. Sharpe ratio measures average return per unit of volatility, annualized using 252 trading days. Max drawdown measures the largest peak-to-trough equity decline.

## Testing

Unit tests verify market-data normalization, duplicate handling, moving-average signals, transaction-cost application, and metric calculations.

Integration tests use FastAPI’s test client with a stubbed market-data provider. That keeps external Yahoo calls out of tests while still verifying the ingest, backtest, and experiment retrieval flow.

Mocks and stubs replace slow or unreliable external dependencies with deterministic test doubles.

## CI

GitHub Actions runs on pushes to `main` and pull requests targeting `main`.

The CI workflow:

1. Installs Python 3.12 dependencies.
2. Starts a PostgreSQL service container.
3. Runs Alembic migrations.
4. Runs Ruff linting.
5. Runs Ruff formatting checks.
6. Runs mypy type checks.
7. Runs pytest.
8. Builds the Docker image.

CI means continuous integration: it verifies the branch is healthy. CD means continuous delivery or deployment: it releases software to an environment. Mercury delays CD because Phase 1 does not yet define a real production environment, secrets process, release policy, or operational monitoring.

## Database Schema

`market_bars` stores normalized OHLCV bars. The unique constraint on `(symbol, timestamp, interval)` prevents accidental duplicate rows, and the index supports symbol/time-range queries.

`experiments` stores one reproducible backtest run. Parameters and metrics use JSON/JSONB because different strategies will later have different parameter and metric shapes.

## Current Limitations

- Only one strategy exists.
- The Yahoo provider is suitable for development, not institutional data quality.
- There is no authentication or authorization.
- There is no production deployment.
- There is no portfolio-level multi-asset backtesting.
- There is no agentic research loop yet.


