# Development

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
```

## Validation

```bash
ruff check .
ruff format --check .
mypy app
python scripts/build_native.py
python -c "import app.backtesting.native._engine"
pytest
alembic heads
```

For database migration validation, run PostgreSQL and set `DATABASE_URL`, then:

```bash
alembic upgrade head
```

Docker:

```bash
docker build .
docker compose up --build
```

Compose runs its dedicated `migrations` service before the API and campaign
worker. When running the image outside Compose, run `alembic upgrade head`
against the target database as a separate deployment step before starting the
application container.

## Useful API Checks

```bash
curl http://localhost:8000/health
curl http://localhost:8000/workflow-versions
curl http://localhost:8000/evals
```
# Developer experience

Install the project in editable mode, then use the CLI:

```bash
python -m pip install -e ".[dev]"
mercury doctor --json
mercury demo
mercury demo --run
```

`doctor` is safe to run without infrastructure: it reports configuration,
PAPER-only mode, PostgreSQL queue design, native-extension availability, data
directory state, and model-routing policy without exposing database secrets.
It does not claim a live database connection is healthy. The canonical demo is
the deterministic offline mission described in `docs/canonical_demo.md`.
