from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.dependencies import get_live_paper_trading_service
from app.market_data.live import StaticLiveMarketDataProvider, live_bar_from_mapping
from app.paper_trading.live_service import LivePaperTradingService


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
    assert "regime_performance" in experiment["run_metadata"]

    get_response = client.get(f"/backtests/{experiment['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == experiment["id"]

    trades_response = client.get(f"/backtests/{experiment['id']}/trades")
    assert trades_response.status_code == 200
    assert len(trades_response.json()) == experiment["metrics"]["number_of_trades"]

    regime_response = client.get(f"/strategies/{experiment['id']}/regime-performance")
    assert regime_response.status_code == 200
    assert regime_response.json()["regime_version"] == "regime-v1"

    report_response = client.get(f"/experiments/{experiment['id']}/report")
    assert report_response.status_code == 200
    report = report_response.json()
    assert report["experiment_id"] == experiment["id"]
    assert report["measured_results"]["sharpe_ratio"] == experiment["metrics"]["sharpe_ratio"]
    assert report["export_metadata"]["formats"] == ["json", "markdown"]

    markdown_response = client.get(f"/experiments/{experiment['id']}/report?format=markdown")
    assert markdown_response.status_code == 200
    assert "## Measured Result" in markdown_response.text

    reproduce_response = client.post(f"/experiments/{experiment['id']}/reproduce")
    assert reproduce_response.status_code == 200
    assert reproduce_response.json()["match"] is True


def test_regime_and_evolution_api_flow(client: TestClient) -> None:
    ingest_response = client.post(
        "/market-data/fetch",
        json={"symbol": "MSFT", "start": "2024-01-01", "end": "2024-02-15", "interval": "1d"},
    )
    assert ingest_response.status_code == 201

    regime_response = client.post(
        "/regimes",
        json={"symbol": "MSFT", "start": "2024-01-01", "end": "2024-02-15", "lookback": 5},
    )
    assert regime_response.status_code == 201
    assert regime_response.json()[0]["regime_version"] == "regime-v1"

    transitions_response = client.get("/regimes/MSFT/transitions")
    assert transitions_response.status_code == 200
    assert transitions_response.json()

    evolution_response = client.post(
        "/evolution-runs",
        json={
            "objective": "Evolve robust moving-average variants for MSFT",
            "symbol": "MSFT",
            "start": "2024-01-01",
            "end": "2024-02-15",
            "initial_population": [
                {"short_window": 2, "long_window": 5},
                {"short_window": 3, "long_window": 8},
            ],
            "generations": 1,
            "population_size": 2,
        },
    )
    assert evolution_response.status_code == 201
    run = evolution_response.json()
    assert run["status"] == "completed"

    population_response = client.get(f"/evolution-runs/{run['id']}/population")
    assert population_response.status_code == 200
    assert len(population_response.json()) == 2

    champion_response = client.get(f"/evolution-runs/{run['id']}/champion")
    assert champion_response.status_code == 200
    assert champion_response.json()["promotion_status"] == "promote"


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


def test_research_agent_eval_and_version_api(client: TestClient) -> None:
    versions_response = client.get("/workflow-versions")
    assert versions_response.status_code == 200
    workflow_version_id = versions_response.json()[0]["id"]

    eval_response = client.post(
        "/evals/run",
        json={
            "benchmark_name": "research_agent_v1",
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


def test_campaign_api_queues_worker_jobs_and_reports(client: TestClient) -> None:
    ingest_response = client.post(
        "/market-data/fetch",
        json={"symbol": "MSFT", "start": "2024-01-01", "end": "2024-01-21", "interval": "1d"},
    )
    assert ingest_response.status_code == 201

    campaign_response = client.post(
        "/campaigns",
        json={
            "objective": "Can medium-term momentum produce robust returns on MSFT?",
            "symbols": ["MSFT"],
            "start_date": "2024-01-01",
            "end_date": "2024-01-21",
            "constraints": {"minimum_trade_count": 0, "max_drawdown": 0.9},
            "split_definition": {
                "train": {"start": "2024-01-01", "end": "2024-01-08"},
                "validation": {"start": "2024-01-08", "end": "2024-01-15"},
                "test": {"start": "2024-01-15", "end": "2024-01-21"},
            },
            "budget": {"max_experiments": 1, "max_optimization_trials": 1},
            "parameter_space": {"short_window": [2], "long_window": [3]},
            "optimization_method": "grid",
        },
    )
    assert campaign_response.status_code == 201
    campaign = campaign_response.json()
    assert campaign["status"] == "created"
    assert len(campaign["generated_hypotheses"]) == 1

    run_response = client.post(f"/campaigns/{campaign['id']}/run", json={})
    assert run_response.status_code == 200
    assert run_response.json()[0]["status"] == "queued"

    worker_response = client.post("/jobs/work", json={"worker_name": "api-test", "max_jobs": 1})
    assert worker_response.status_code == 200
    assert worker_response.json()[0]["status"] == "succeeded"

    ranking_response = client.get(f"/campaigns/{campaign['id']}/rankings")
    assert ranking_response.status_code == 200
    assert ranking_response.json()[0]["rank"] == 1

    report_response = client.get(f"/campaigns/{campaign['id']}/report")
    assert report_response.status_code == 200
    assert report_response.json()["hypotheses_tested"] == 1
    assert report_response.json()["test_results"][0]["test_experiment_id"] is not None
    assert "strategy_evolution" in report_response.json()
    assert report_response.json()["artifact"]["artifact_type"] == "campaign"


def test_paper_trading_api_replays_market_data_to_portfolio(client: TestClient) -> None:
    ingest_response = client.post(
        "/market-data/fetch",
        json={"symbol": "MSFT", "start": "2024-01-01", "end": "2024-01-12", "interval": "1d"},
    )
    assert ingest_response.status_code == 201

    session_response = client.post(
        "/paper-trading/sessions",
        json={
            "symbol": "MSFT",
            "start": "2024-01-01",
            "end": "2024-01-12",
            "interval": "1d",
            "strategy_parameters": {"fast_window": 2, "slow_window": 3},
            "initial_cash": 10000,
            "commission_bps": 1,
            "slippage_bps": 2,
        },
    )
    assert session_response.status_code == 201
    paper_session = session_response.json()
    assert paper_session["status"] == "completed"
    assert paper_session["execution_mode"] == "PAPER"
    assert paper_session["metrics"]["market_events"] == 11

    orders_response = client.get(f"/paper-trading/sessions/{paper_session['id']}/orders")
    assert orders_response.status_code == 200
    assert all(order["status"] in {"SUBMITTED", "REJECTED"} for order in orders_response.json())

    trades_response = client.get(f"/paper-trading/sessions/{paper_session['id']}/trades")
    assert trades_response.status_code == 200
    assert len(trades_response.json()) == paper_session["metrics"]["fills"]

    portfolio_response = client.get(f"/paper-trading/sessions/{paper_session['id']}/portfolio")
    assert portfolio_response.status_code == 200
    assert portfolio_response.json()["equity"] == paper_session["metrics"]["ending_equity"]


def test_live_paper_trading_api_runs_bounded_fake_feed(
    client: TestClient,
    db_session: Session,
) -> None:
    ingest_response = client.post(
        "/market-data/fetch",
        json={"symbol": "MSFT", "start": "2024-01-01", "end": "2024-01-04", "interval": "1m"},
    )
    assert ingest_response.status_code == 201
    factory = sessionmaker(
        bind=db_session.bind,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    live_provider = StaticLiveMarketDataProvider(
        [
            live_bar_from_mapping(
                {
                    "Datetime": datetime(2024, 1, 2, 14, 30 + index, tzinfo=UTC),
                    "Open": close,
                    "High": close + 1,
                    "Low": close - 1,
                    "Close": close,
                    "Volume": 1_000 + index,
                },
                symbol="MSFT",
                interval="1m",
                source="test",
            )
            for index, close in enumerate([103, 104, 98])
        ]
    )
    client.app.dependency_overrides[get_live_paper_trading_service] = lambda: (
        LivePaperTradingService(factory, live_provider)
    )

    session_response = client.post(
        "/live/sessions",
        json={
            "symbol": "MSFT",
            "interval": "1m",
            "strategy_parameters": {"fast_window": 2, "slow_window": 3},
            "warmup_start": "2024-01-01",
            "warmup_end": "2024-01-04",
            "max_events": 3,
            "initial_cash": 10000,
        },
    )

    assert session_response.status_code == 201
    live_session = session_response.json()
    assert live_session["execution_mode"] == "PAPER"
    assert live_session["status"] == "STOPPED"

    metrics_response = client.get(f"/live/sessions/{live_session['id']}/metrics")
    assert metrics_response.status_code == 200
    assert metrics_response.json()["market_events_received"] == 3
    assert "processing_latency" in metrics_response.json()

    portfolio_response = client.get(f"/live/sessions/{live_session['id']}/portfolio")
    assert portfolio_response.status_code == 200
    assert portfolio_response.json()["equity"] > 0

    orders_response = client.get(f"/live/sessions/{live_session['id']}/orders")
    assert orders_response.status_code == 200

    health_response = client.get("/live/health")
    assert health_response.status_code == 200
    assert {item["component"] for item in health_response.json()} >= {"Market Data", "Database"}
