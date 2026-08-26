from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.campaigns.optimization import generate_parameter_variants
from app.campaigns.schemas import CampaignCreateRequest
from app.campaigns.service import CampaignService
from app.models.campaign import CampaignJob
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
