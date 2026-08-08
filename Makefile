.PHONY: install lint format format-check typecheck test migrate run docker-up

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

migrate:
	alembic upgrade head

run:
	uvicorn app.main:app --reload

docker-up:
	docker compose up --build

