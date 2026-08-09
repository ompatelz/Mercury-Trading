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

## Useful API Checks

```bash
curl http://localhost:8000/health
curl http://localhost:8000/workflow-versions
curl http://localhost:8000/evals
```
