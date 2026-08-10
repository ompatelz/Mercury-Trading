from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.campaigns.optimization import generate_parameter_variants
from app.campaigns.schemas import CampaignCreateRequest
from app.campaigns.service import CampaignService
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
    db_session.commit()

    assert len(jobs) == 2

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
