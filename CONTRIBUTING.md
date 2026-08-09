# Contributing

Mercury changes should preserve reproducibility and deterministic validation.

Before opening a PR, run:

```bash
ruff check .
ruff format --check .
mypy app
python scripts/build_native.py
pytest
```

Database changes need an Alembic migration and tests covering the service or API
behavior that depends on the schema. Agent or workflow changes should include an
eval result or a deterministic test explaining why the change is better.
