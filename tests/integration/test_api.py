from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "Mercury"}


def test_ingest_and_backtest_flow(client: TestClient) -> None:
    ingest_response = client.post(
        "/market-data/fetch",
        json={"symbol": "MSFT", "start": "2024-01-01", "end": "2024-01-11", "interval": "1d"},
    )
    assert ingest_response.status_code == 201
    assert ingest_response.json()["rows_inserted"] == 10

    bars_response = client.get("/market-data/MSFT?start=2024-01-01&end=2024-01-11")
    assert bars_response.status_code == 200
    assert len(bars_response.json()) == 10

    backtest_response = client.post(
        "/backtests",
        json={
            "symbol": "MSFT",
            "start": "2024-01-01",
            "end": "2024-01-11",
            "interval": "1d",
            "short_window": 2,
            "long_window": 3,
            "initial_capital": 10000,
            "transaction_cost_bps": 1,
            "slippage_bps": 2,
        },
    )
    assert backtest_response.status_code == 201
    experiment = backtest_response.json()
    assert experiment["strategy_name"] == "moving_average_crossover"
    assert "sharpe_ratio" in experiment["metrics"]
    assert "sortino_ratio" in experiment["metrics"]
    assert experiment["run_metadata"]["candles_processed"] == 10

    get_response = client.get(f"/backtests/{experiment['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == experiment["id"]

    trades_response = client.get(f"/backtests/{experiment['id']}/trades")
    assert trades_response.status_code == 200
    assert len(trades_response.json()) == experiment["metrics"]["number_of_trades"]


def test_research_experiment_flow(client: TestClient) -> None:
    ingest_response = client.post(
        "/market-data/fetch",
        json={"symbol": "MSFT", "start": "2024-01-01", "end": "2024-01-11", "interval": "1d"},
    )
    assert ingest_response.status_code == 201

    response = client.post(
        "/research/experiments",
        json={
            "objective": "Explore trend-following behavior on MSFT with deterministic data",
            "symbol": "MSFT",
            "start_date": "2024-01-01",
            "end_date": "2024-01-11",
            "interval": "1d",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["strategy"]["strategy"] == "moving_average_crossover"
    assert payload["backtest_experiment_id"] is not None
    assert payload["model_metadata"]["provider"] == "local"
    assert payload["report"]["performance_metrics"] == payload["metrics"]
    assert payload["workflow_metadata"]["retrieved_memory_count"] == 0

    memory_response = client.get(f"/experiments/{payload['id']}/memory")
    assert memory_response.status_code == 200
    assert len(memory_response.json()) == 1

    trace_response = client.get(f"/research/experiments/{payload['id']}/trace")
    assert trace_response.status_code == 200
    assert {event["event_type"] for event in trace_response.json()} == {
        "memory_retrieved",
        "lesson_created",
    }


def test_phase4_eval_and_version_api(client: TestClient) -> None:
    versions_response = client.get("/workflow-versions")
    assert versions_response.status_code == 200
    workflow_version_id = versions_response.json()[0]["id"]

    eval_response = client.post(
        "/evals/run",
        json={
            "benchmark_name": "phase4_research_agent_v1",
            "workflow_version_id": workflow_version_id,
        },
    )
    assert eval_response.status_code == 201
    eval_payload = eval_response.json()
    assert eval_payload["aggregate_metrics"]["task_success_rate"] == 1.0

    tasks_response = client.get(f"/evals/{eval_payload['id']}/tasks")
    assert tasks_response.status_code == 200
    assert len(tasks_response.json()) == 4

    comparison_response = client.post(
        "/evals/compare",
        json={
            "baseline_eval_run_id": eval_payload["id"],
            "candidate_eval_run_id": eval_payload["id"],
        },
    )
    assert comparison_response.status_code == 201
    assert comparison_response.json()["decision"] == "promote"
