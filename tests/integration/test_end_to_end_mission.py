from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.campaigns.schemas import CampaignCreateRequest
from app.campaigns.service import CampaignService
from app.memory.service import ResearchMemoryService
from app.models.market_data import MarketBar
from app.production_simulation.schemas import ProductionSimulationCreateRequest
from app.production_simulation.service import ProductionSimulationService
from app.research_artifacts.service import ResearchArtifactService
from app.research_intelligence.schemas import HypothesisProposal
from app.research_intelligence.service import ResearchIntelligenceService


def test_canonical_paper_only_research_mission(db_session: Session) -> None:
    _seed_bars(db_session, days=130)
    campaign_service = CampaignService(db_session)
    campaign = campaign_service.create_campaign(
        CampaignCreateRequest(
            objective="Find robust medium-term MSFT momentum under costs and drawdown limits.",
            symbols=["MSFT"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 4, 30),
            constraints={
                "minimum_trade_count": 0,
                "max_drawdown": 0.9,
                "require_stress_testing": True,
                "stress_simulations": 10,
            },
            budget={"max_experiments": 2, "max_optimization_trials": 2},
            datasets={"available_data": ["prices"]},
            parameter_space={"short_window": [2, 3], "long_window": [5]},
        )
    )
    memories = ResearchMemoryService(db_session).retrieve_for_research(
        campaign.objective, "MSFT", as_of=campaign.end_date
    )
    triage = ResearchIntelligenceService(db_session).triage(
        campaign.id,
        HypothesisProposal(
            claim="Medium-term momentum can remain robust after explicit trading costs.",
            intuition="Persistent directional moves may survive conservative cost assumptions.",
            required_data=("prices",),
            strategy_family="moving_average_crossover",
            expected_regime="trending",
            holding_period="medium-term",
            falsification_criteria=("Validation Sharpe is non-positive.",),
            major_risks=("Regime reversal",),
            expected_research_cost=0.0,
        ),
    )
    jobs = campaign_service.run_campaign(campaign.id)
    while campaign_service.process_next_job("canonical-demo-worker") is not None:
        pass
    db_session.refresh(campaign)
    artifact = ResearchArtifactService(db_session).campaign_artifact(campaign.id)
    simulation = ProductionSimulationService(db_session).create_and_run(
        ProductionSimulationCreateRequest(
            universe=["MSFT"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 4, 30),
            research_window_days=30,
            deployment_window_days=30,
            candidates=[
                {
                    "version": "canonical-demo:v1",
                    "parameters": {"fast_window": 2, "slow_window": 5},
                    "expected_sharpe": 0.1,
                    "as_of": "2024-01-01",
                }
            ],
            max_drawdown=0.9,
        )
    )

    assert jobs
    assert triage.accepted
    assert memories == []
    assert campaign.status == "completed"
    assert campaign.budget_used["experiments"] == 2
    assert artifact.artifact_type == "campaign"
    assert artifact.conclusion["final_conclusions"] == campaign.final_conclusions
    assert simulation.execution_model["mode"] == "SHADOW"
    assert simulation.status == "COMPLETED"
    assert simulation.timeline
    assert simulation.timeline[0]["paper_session_id"]


def _seed_bars(session: Session, days: int) -> None:
    start = datetime(2024, 1, 1)
    session.add_all(
        MarketBar(
            symbol="MSFT",
            timestamp=start + timedelta(days=index),
            interval="1d",
            open=Decimal(str(100 + index * 0.4)),
            high=Decimal(str(101 + index * 0.4)),
            low=Decimal(str(99 + index * 0.4)),
            close=Decimal(str(100.5 + index * 0.4)),
            volume=1_000 + index,
        )
        for index in range(days)
    )
    session.flush()
