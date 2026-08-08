.PHONY: install lint format format-check typecheck test benchmark migrate run docker-up

install:
	pip install -e ".[dev]"

lint:
	ruff check .

format:
	ruff format .

format-check:
	ruff format --check .

typecheck:
	mypy app

test:
	pytest

benchmark:
	python scripts/benchmark_backtest.py --rows 10000

migrate:
	alembic upgrade head

run:
	uvicorn app.main:app --reload

docker-up:
	docker compose up --build

