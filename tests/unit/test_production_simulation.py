from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.market_data import MarketBar
from app.production_simulation.schemas import ProductionSimulationCreateRequest
from app.production_simulation.service import ProductionSimulationService


def test_walk_forward_simulation_freezes_strategy_and_replays_shadow_windows(
    db_session: Session,
) -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    db_session.add_all(
        [
            MarketBar(
                symbol="MSFT",
                timestamp=start + timedelta(days=i),
                interval="1d",
                open=Decimal(str(100 + i)),
                high=Decimal(str(101 + i)),
                low=Decimal(str(99 + i)),
                close=Decimal(str(100 + i)),
                volume=1_000,
            )
            for i in range(20)
        ]
    )
    db_session.flush()

    result = ProductionSimulationService(db_session).create_and_run(
        ProductionSimulationCreateRequest(
            universe=["MSFT"],
            start_date=start.date(),
            end_date=(start + timedelta(days=20)).date(),
            research_window_days=5,
            deployment_window_days=5,
            strategy_parameters={"fast_window": 2, "slow_window": 3},
        )
    )

    assert result.status == "COMPLETED"
    assert result.metrics["research_cycles"] == 3
    assert result.metrics["events_processed"] > 0
    assert all(item["lifecycle"] == "ACTIVE" for item in result.timeline)
    assert all(
        item["strategy_version"] == "moving_average_crossover:v1" for item in result.timeline
    )
    assert all(
        item["research_end"] <= item["deployment_start"] <= item["deployment_end"]
        for item in result.timeline
    )
    assert all(item["expected"]["as_of"] == item["research_end"] for item in result.timeline)


def test_candidate_promotion_is_manifest_and_time_gated(db_session: Session) -> None:
    start = datetime(2024, 1, 1, tzinfo=UTC)
    db_session.add_all(
        [
            MarketBar(
                symbol="MSFT",
                timestamp=start + timedelta(days=i),
                interval="1d",
                open=100 + i,
                high=101 + i,
                low=99 + i,
                close=100 + i,
                volume=1_000,
            )
            for i in range(12)
        ]
    )
    db_session.flush()
    result = ProductionSimulationService(db_session).create_and_run(
        ProductionSimulationCreateRequest(
            universe=["MSFT"],
            start_date=start.date(),
            end_date=(start + timedelta(days=12)).date(),
            research_window_days=3,
            deployment_window_days=3,
            strategy_parameters={"fast_window": 2, "slow_window": 3},
            candidates=[
                {
                    "version": "future-challenger:v2",
                    "parameters": {"fast_window": 1, "slow_window": 2},
                    "expected_sharpe": 99,
                    "as_of": "2025-01-01",
                },
                {
                    "version": "approved-challenger:v2",
                    "parameters": {"fast_window": 2, "slow_window": 4},
                    "expected_sharpe": 1.5,
                    "as_of": "2024-01-04",
                    "promoted": True,
                },
            ],
        )
    )
    assert all(item["strategy_version"] != "future-challenger:v2" for item in result.timeline)
    assert "approved-challenger:v2" in result.strategy_versions
    assert any(item["state"] == "RETIRED" for item in result.metrics["champion_lifecycle"])
