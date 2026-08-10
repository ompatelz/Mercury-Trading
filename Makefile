.PHONY: install lint format format-check typecheck native-build test benchmark migrate run worker docker-up

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

native-build:
	python scripts/build_native.py

test:
	pytest

benchmark:
	python scripts/benchmark_backtest.py --rows 10000

migrate:
	alembic upgrade head

run:
	uvicorn app.main:app --reload

worker:
	python scripts/run_worker.py

docker-up:
	docker compose up --build

