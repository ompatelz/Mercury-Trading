# Testing and Validation

Local CI-equivalent checks:

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

Database migration check:

```bash
alembic upgrade head
```

Worker smoke check after creating queued jobs:

```bash
python scripts/run_worker.py --worker-name local-worker --max-jobs 1
```

GitHub Actions now covers Python quality/tests, PostgreSQL migrations, native
C++ build/import/parity, campaign worker integration, Docker build, and repo
hygiene.

Normal CI must not require paid external LLM calls. Campaign and eval tests use
deterministic local behavior.

Regime and evolution tests cover:

- deterministic classification
- synthetic bullish/bearish regimes
- no future leakage
- regime-version persistence
- transition summaries
- per-regime metrics and robustness flags
- strategy specification validation
- bounded mutation and compatible crossover
- memory-influenced mutation provenance
- fitness and champion/challenger rules
- persisted evolution lineage and reports
