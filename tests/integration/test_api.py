from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "Mercury"}


def test_ingest_and_backtest_flow(client: TestClient) -> None:
    ingest_response = client.post(
        "/market-data/ingest",
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
        },
    )
    assert backtest_response.status_code == 201
    experiment = backtest_response.json()
    assert experiment["strategy_name"] == "moving_average_crossover"
    assert "sharpe_ratio" in experiment["metrics"]

    get_response = client.get(f"/experiments/{experiment['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == experiment["id"]
