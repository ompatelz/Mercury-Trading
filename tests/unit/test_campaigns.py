from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.campaigns.optimization import generate_parameter_variants
from app.campaigns.schemas import CampaignCreateRequest
from app.campaigns.service import CampaignService
from app.data.service import DataLineageService, FeatureStore
from app.experiments.service import _bars_to_frame
from app.models.campaign import CampaignJob
from app.models.experiment import Experiment
from app.models.market_data import MarketBar


def test_grid_random_and_bayesian_parameter_search_respect_window_order() -> None:
    space = {"short_window": [2, 5], "long_window": [3, 8]}

    for method in ["grid", "random", "bayesian"]:
        variants = generate_parameter_variants(space, method=method, max_variants=3)

        assert variants
        assert all(int(item["short_window"]) < int(item["long_window"]) for item in variants)


def test_campaign_worker_runs_jobs_and_builds_rankings(db_session: Session) -> None:
    _seed_bars(db_session, symbol="MSFT", days=45)
    service = CampaignService(db_session)
    campaign = service.create_campaign(
        CampaignCreateRequest(
            objective="Can medium-term momentum produce robust returns on MSFT?",
            symbols=["MSFT"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 2, 15),
            constraints={"minimum_trade_count": 0, "max_drawdown": 0.9},
            budget={"max_experiments": 2, "max_optimization_trials": 2},
            parameter_space={"short_window": [2, 3], "long_window": [5, 8]},
            optimization_method="grid",
        )
    )
    jobs = service.run_campaign(campaign.id)
    duplicate_jobs = service.run_campaign(campaign.id)
    db_session.commit()

    assert len(jobs) == 2
    assert duplicate_jobs == []

    processed_one = service.process_next_job("test-worker")
    processed_two = service.process_next_job("test-worker")
    db_session.commit()

    assert processed_one is not None
    assert processed_two is not None
    db_session.refresh(campaign)
    assert campaign.status == "completed"
    assert int(campaign.budget_used["experiments"]) == 2
    assert service.list_rankings(campaign.id)
    assert service.list_portfolios(campaign.id)
    assert campaign.final_conclusions["hypotheses_tested"] == 2
    assert campaign.final_conclusions["test_results"]
    assert campaign.final_conclusions["split_definition"]["test"]["start"] == "2024-02-06"
    experiments = service.list_experiments(campaign.id)
    walk_forward_windows = experiments[0].evaluation["walk_forward_windows"]
    assert walk_forward_windows
    assert all(
        window["test_end"] <= campaign.final_conclusions["split_definition"]["test"]["start"]
        for window in walk_forward_windows
    )
    assert all(window["uses_locked_test_split"] is False for window in walk_forward_windows)


def test_campaign_backtests_inherit_dataset_snapshot_and_features(
    db_session: Session,
) -> None:
    _seed_bars(db_session, symbol="MSFT", days=45)
    data_version = DataLineageService(db_session).create_dataset_version(
        name="MSFT_1d",
        bars=_bars_to_frame(list(db_session.query(MarketBar).filter_by(symbol="MSFT"))),
        provider="test",
        frequency="1d",
    )
    feature = FeatureStore(db_session).register(
        name="msft_close_return",
        version="v1",
        implementation="returns",
        lookback=1,
    )
    snapshot = DataLineageService(db_session).create_snapshot(
        "msft-research-snapshot",
        [data_version.id],
        feature_set=[{"feature_version_id": str(feature.id)}],
    )
    service = CampaignService(db_session)

    campaign = service.create_campaign(
        CampaignCreateRequest(
            objective="Can snapshot-locked inputs run through the campaign worker?",
            symbols=["MSFT"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 2, 15),
            constraints={"minimum_trade_count": 0},
            budget={"max_experiments": 1, "max_optimization_trials": 1},
            parameter_space={"short_window": [2], "long_window": [5]},
            dataset_snapshot_id=snapshot.id,
            feature_set=snapshot.feature_set,
        )
    )
    service.run_campaign(campaign.id)
    job = service.process_next_job("test-worker")
    db_session.commit()

    assert job is not None
    planned = service.list_experiments(campaign.id)[0]
    assert planned.experiment_id is not None
    experiment = db_session.get(Experiment, planned.experiment_id)
    assert experiment is not None
    assert experiment.dataset_version_id == data_version.id
    assert experiment.feature_versions == [
        {
            "feature_version_id": str(feature.id),
            "dataset_version_id": str(data_version.id),
            "row_count": 45,
        }
    ]


def test_job_cancellation_and_stale_worker_recovery(db_session: Session) -> None:
    service = CampaignService(db_session)
    campaign = service.create_campaign(
        CampaignCreateRequest(
            objective="Can deterministic jobs safely recover after a worker lease expires?",
            symbols=["MSFT"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 2, 15),
            parameter_space={"short_window": [2], "long_window": [5]},
        )
    )
    job = service.run_campaign(campaign.id)[0]
    cancelled = service.cancel_job(job.id)

    assert cancelled.status == "CANCELLED"
    assert service.claim_next_job("worker-a") is None

    stale_job = CampaignJob(
        campaign_id=campaign.id,
        campaign_experiment_id=None,
        job_type="RUN_BACKTEST",
        status="RUNNING",
        payload={"version": 1},
        idempotency_key="stale-job",
        worker="lost-worker",
        attempt_count=1,
        max_attempts=3,
        heartbeat_at=None,
        retry_history=[],
    )
    db_session.add(stale_job)
    db_session.flush()

    assert service.recover_stale_jobs(stale_after_seconds=1) == 1
    assert stale_job.status == "RETRYING"
    assert stale_job.error_type == "RuntimeError"
    assert stale_job.retry_history[0]["retryable"] is True


def test_deterministic_job_failure_is_not_retried(db_session: Session) -> None:
    service = CampaignService(db_session)
    campaign = service.create_campaign(
        CampaignCreateRequest(
            objective="Can invalid worker jobs fail without an unsafe retry loop?",
            symbols=["MSFT"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 2, 15),
            parameter_space={"short_window": [2], "long_window": [5]},
        )
    )
    job = CampaignJob(
        campaign_id=campaign.id,
        campaign_experiment_id=None,
        job_type="INVALID_JOB",
        status="QUEUED",
        payload={"version": 1},
        idempotency_key="invalid-job",
        retry_history=[],
    )
    db_session.add(job)
    db_session.flush()

    result = service.process_next_job("worker-a")

    assert result is not None
    assert result.status == "FAILED"
    assert result.attempt_count == 1
    assert result.error_type == "ValueError"


def test_transient_database_failure_retries_without_duplicate_experiment(
    db_session: Session, monkeypatch
) -> None:
    _seed_bars(db_session, symbol="MSFT", days=45)
    service = CampaignService(db_session)
    campaign = service.create_campaign(
        CampaignCreateRequest(
            objective="Can temporary database failures recover safely?",
            symbols=["MSFT"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 2, 15),
            budget={"max_experiments": 1, "max_optimization_trials": 1},
            parameter_space={"short_window": [2], "long_window": [5]},
        )
    )
    job = service.run_campaign(campaign.id)[0]
    original = service._run_campaign_experiment
    attempts = 0

    def fail_once(current_job: CampaignJob) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ConnectionError("database temporarily unavailable")
        original(current_job)

    monkeypatch.setattr(service, "_run_campaign_experiment", fail_once)
    first = service.process_next_job("worker-a")

    assert first is not None
    assert first.status == "RETRYING"
    assert first.id == job.id
    first.available_at = service._database_now()
    second = service.process_next_job("worker-b")

    assert second is not None
    assert second.status == "SUCCEEDED"
    assert attempts == 2
    assert len(service.list_jobs(campaign.id)) == 1
    assert (
        len([item for item in service.list_experiments(campaign.id) if item.status == "completed"])
        == 1
    )


def test_interrupted_campaign_restores_only_missing_durable_jobs(db_session: Session) -> None:
    service = CampaignService(db_session)
    campaign = service.create_campaign(
        CampaignCreateRequest(
            objective="Can an interrupted submission recover without duplicates?",
            symbols=["MSFT"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 2, 15),
            budget={"max_experiments": 2, "max_optimization_trials": 2},
            parameter_space={"short_window": [2, 3], "long_window": [5]},
        )
    )
    jobs = service.run_campaign(campaign.id)
    missing_job = jobs.pop()
    db_session.delete(missing_job)
    db_session.flush()

    assert service.recover_interrupted_campaigns() == 1
    restored = service.list_jobs(campaign.id)

    assert len(restored) == 2
    assert len({job.idempotency_key for job in restored}) == 2
    assert len({job.campaign_experiment_id for job in restored}) == 2


def _seed_bars(session: Session, symbol: str, days: int) -> None:
    start = datetime(2024, 1, 1)
    bars = []
    for index in range(days):
        price = 100 + index * 0.8 + (index % 5) * 0.2
        bars.append(
            MarketBar(
                symbol=symbol,
                timestamp=start + timedelta(days=index),
                interval="1d",
                open=Decimal(str(price)),
                high=Decimal(str(price + 1)),
                low=Decimal(str(price - 1)),
                close=Decimal(str(price + 0.5)),
                volume=1_000 + index,
            )
        )
    session.add_all(bars)
    session.flush()
