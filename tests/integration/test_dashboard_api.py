from fastapi.testclient import TestClient


def test_dashboard_exposes_research_observability_flow(client: TestClient) -> None:
    ingest_response = client.post(
        "/market-data/fetch",
        json={"symbol": "MSFT", "start": "2024-01-01", "end": "2024-02-15", "interval": "1d"},
    )
    assert ingest_response.status_code == 201

    campaign_response = client.post(
        "/campaigns",
        json={
            "objective": "Find robust moving average momentum variants for MSFT",
            "symbols": ["MSFT"],
            "start_date": "2024-01-01",
            "end_date": "2024-02-15",
            "constraints": {"minimum_trade_count": 0, "max_drawdown": 0.9},
            "split_definition": {
                "train": {"start": "2024-01-01", "end": "2024-01-15"},
                "validation": {"start": "2024-01-15", "end": "2024-02-01"},
                "test": {"start": "2024-02-01", "end": "2024-02-15"},
            },
            "budget": {"max_experiments": 1, "max_optimization_trials": 1},
            "parameter_space": {"short_window": [2], "long_window": [3]},
            "optimization_method": "grid",
        },
    )
    assert campaign_response.status_code == 201
    campaign = campaign_response.json()

    run_response = client.post(f"/campaigns/{campaign['id']}/run", json={})
    assert run_response.status_code == 200
    worker_response = client.post("/jobs/work", json={"worker_name": "dashboard-test"})
    assert worker_response.status_code == 200

    experiments_response = client.get("/dashboard/experiments?symbol=MSFT&limit=10")
    assert experiments_response.status_code == 200
    experiments = experiments_response.json()
    assert experiments["total"] >= 1
    experiment_id = experiments["items"][0]["id"]
    assert experiments["items"][0]["strategy_name"] == "moving_average_crossover"

    overview_response = client.get("/dashboard/overview")
    assert overview_response.status_code == 200
    overview = overview_response.json()
    metric_labels = {item["label"] for item in overview["metrics"]}
    assert {"Experiments Run", "Active Campaigns", "Research Success Rate"} <= metric_labels
    assert overview["system_health"][0]["component"] == "API"

    detail_response = client.get(f"/dashboard/experiments/{experiment_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["research_context"]["dataset_period"]["interval"] == "1d"
    assert "sharpe_ratio" in detail["performance"]
    assert isinstance(detail["regime_weaknesses"], list)

    campaign_detail_response = client.get(f"/dashboard/campaigns/{campaign['id']}")
    assert campaign_detail_response.status_code == 200
    campaign_detail = campaign_detail_response.json()
    assert campaign_detail["objective"] == campaign["objective"]
    assert campaign_detail["experiment_count"] == 1
    assert campaign_detail["current_best_candidate"] is not None


def test_dashboard_lineage_comparison_and_paper_monitoring(client: TestClient) -> None:
    ingest_response = client.post(
        "/market-data/fetch",
        json={"symbol": "MSFT", "start": "2024-01-01", "end": "2024-02-15", "interval": "1d"},
    )
    assert ingest_response.status_code == 201

    evolution_response = client.post(
        "/evolution-runs",
        json={
            "objective": "Evolve dashboard-visible moving-average variants",
            "symbol": "MSFT",
            "start": "2024-01-01",
            "end": "2024-02-15",
            "initial_population": [
                {"short_window": 2, "long_window": 5},
                {"short_window": 3, "long_window": 8},
            ],
            "generations": 2,
            "population_size": 2,
        },
    )
    assert evolution_response.status_code == 201
    run = evolution_response.json()

    population_response = client.get(f"/evolution-runs/{run['id']}/population")
    assert population_response.status_code == 200
    population = population_response.json()
    champion = next(item for item in population if item["promotion_status"] == "promote")
    challenger = next(item for item in population if item["id"] != champion["id"])

    lineage_response = client.get(f"/dashboard/strategies/{champion['id']}/lineage")
    assert lineage_response.status_code == 200
    lineage = lineage_response.json()
    assert lineage["evolution_run_id"] == run["id"]
    assert len(lineage["nodes"]) == len(population)
    assert lineage["edges"]

    compare_response = client.get(
        f"/dashboard/strategies/compare?champion_id={champion['id']}"
        f"&challenger_id={challenger['id']}"
    )
    assert compare_response.status_code == 200
    comparison = compare_response.json()
    assert comparison["champion_id"] == champion["id"]
    assert comparison["challenger_id"] == challenger["id"]
    assert comparison["decision"] in {"promote", "reject"}
    assert comparison["promotion_criteria"]["population_size"] == 2

    session_response = client.post(
        "/paper-trading/sessions",
        json={
            "symbol": "MSFT",
            "start": "2024-01-01",
            "end": "2024-01-12",
            "interval": "1d",
            "strategy_parameters": {"fast_window": 2, "slow_window": 3},
            "initial_cash": 10000,
        },
    )
    assert session_response.status_code == 201
    paper_session = session_response.json()

    monitor_response = client.get(f"/dashboard/paper-trading/sessions/{paper_session['id']}")
    assert monitor_response.status_code == 200
    monitor = monitor_response.json()
    assert monitor["execution_mode"] == "PAPER"
    assert monitor["equity"] == paper_session["metrics"]["ending_equity"]
    assert monitor["analytics"]["order_count"] >= monitor["analytics"]["filled_order_count"]
    assert monitor["analytics"]["fill_count"] == paper_session["metrics"]["fills"]
    assert 0 <= monitor["analytics"]["fill_rate"] <= 1
    assert monitor["analytics"]["total_notional"] >= 0
    assert monitor["analytics"]["total_fees"] >= 0
    assert monitor["analytics"]["total_slippage_cost"] >= 0
    assert {item["component"] for item in monitor["system_health"]} >= {
        "Paper Broker",
        "Strategy Runner",
    }
