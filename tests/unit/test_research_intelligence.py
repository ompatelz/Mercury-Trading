from datetime import date

from sqlalchemy.orm import Session

from app.campaigns.schemas import CampaignCreateRequest
from app.campaigns.service import CampaignService
from app.research_intelligence.schemas import HypothesisProposal
from app.research_intelligence.service import ResearchIntelligenceService


def _campaign(session: Session):
    return CampaignService(session).create_campaign(
        CampaignCreateRequest(
            objective="Test robust medium-term research hypotheses with known inputs",
            symbols=["MSFT"],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 1),
            datasets={"available_data": ["prices", "volume"]},
            budget={"max_api_cost": 10.0},
        )
    )


def _proposal(
    claim: str = "Momentum persists after a low-volatility trend breakout",
) -> HypothesisProposal:
    return HypothesisProposal(
        claim=claim,
        intuition="Investors underreact to persistent trends.",
        required_data=("prices",),
        strategy_family="moving_average_crossover",
        expected_regime="trending",
        holding_period="weeks",
        falsification_criteria=("negative out-of-sample IC",),
        major_risks=("whipsaw",),
        expected_research_cost=1.0,
    )


def test_triage_rejects_unavailable_data_and_duplicates(db_session: Session) -> None:
    campaign = _campaign(db_session)
    service = ResearchIntelligenceService(db_session)
    accepted = service.triage(campaign.id, _proposal())
    duplicate = service.triage(campaign.id, _proposal())
    unavailable = service.triage(
        campaign.id,
        _proposal("Use fundamentals to predict trend persistence").model_copy(
            update={"required_data": ("fundamentals",)}
        ),
    )
    assert accepted.accepted
    assert not duplicate.accepted and "DUPLICATE_HYPOTHESIS" in duplicate.rejection_reasons
    assert not unavailable.accepted and "UNAVAILABLE_DATA" in unavailable.rejection_reasons
    assert len(campaign.research_queue) == 1
