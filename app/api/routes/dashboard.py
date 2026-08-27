from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.dashboard.schemas import (
    CampaignDashboardResponse,
    DashboardOverviewResponse,
    ExperimentDetailResponse,
    ExperimentListResponse,
    ModelRoutingDashboardResponse,
    PaperTradingDashboardResponse,
    StrategyComparisonResponse,
    StrategyLineageResponse,
)
from app.dashboard.service import DashboardService
from app.db.session import get_session
from app.evals.service import EvalService
from app.model_routing.tracking import ModelUsageService
from app.production_simulation.schemas import ProductionSimulationResponse
from app.strategy_health.schemas import StrategyHealthTimelineResponse
from app.strategy_health.service import StrategyHealthService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/simulations/{simulation_id}", response_model=ProductionSimulationResponse)
def get_dashboard_simulation(
    simulation_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> ProductionSimulationResponse:
    from app.production_simulation.service import ProductionSimulationService

    result = ProductionSimulationService(session).get(simulation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="simulation not found")
    return ProductionSimulationResponse.model_validate(result)


@router.get("/evals")
def get_dashboard_evals(
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    """Evidence-only view for the dashboard's champion/challenger section."""
    service = EvalService(session)
    return {
        "experiments": [
            {
                "id": str(item.id),
                "decision": item.decision,
                "reason": item.reason,
                "comparison": item.comparison,
                "benchmark_name": item.benchmark_name,
                "created_at": item.created_at.isoformat(),
            }
            for item in service.list_experiments()
        ]
    }


@router.get("/model-routing", response_model=ModelRoutingDashboardResponse)
def get_model_routing_dashboard(
    session: Annotated[Session, Depends(get_session)],
) -> ModelRoutingDashboardResponse:
    return ModelRoutingDashboardResponse(usage=ModelUsageService(session).summary())


@router.get("/overview", response_model=DashboardOverviewResponse)
def get_dashboard_overview(
    session: Annotated[Session, Depends(get_session)],
) -> DashboardOverviewResponse:
    return DashboardService(session).overview()


@router.get("/experiments", response_model=ExperimentListResponse)
def list_dashboard_experiments(
    session: Annotated[Session, Depends(get_session)],
    strategy_family: str | None = None,
    symbol: str | None = None,
    campaign_id: UUID | None = None,
    status: str | None = None,
    regime: str | None = None,
    risk_flag: str | None = None,
    agent_version: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ExperimentListResponse:
    return DashboardService(session).list_experiments(
        strategy_family=strategy_family,
        symbol=symbol,
        campaign_id=campaign_id,
        status=status,
        regime=regime,
        risk_flag=risk_flag,
        agent_version=agent_version,
        limit=limit,
        offset=offset,
    )


@router.get("/experiments/{experiment_id}", response_model=ExperimentDetailResponse)
def get_dashboard_experiment(
    experiment_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> ExperimentDetailResponse:
    detail = DashboardService(session).experiment_detail(experiment_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="experiment not found")
    return detail


@router.get("/campaigns/{campaign_id}", response_model=CampaignDashboardResponse)
def get_dashboard_campaign(
    campaign_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> CampaignDashboardResponse:
    detail = DashboardService(session).campaign_detail(campaign_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="campaign not found")
    return detail


@router.get("/strategies/{strategy_id}/lineage", response_model=StrategyLineageResponse)
def get_strategy_lineage(
    strategy_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> StrategyLineageResponse:
    lineage = DashboardService(session).strategy_lineage(strategy_id)
    if lineage is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="strategy not found")
    return lineage


@router.get("/strategies/{strategy_id}/lifecycle", response_model=StrategyHealthTimelineResponse)
def get_strategy_lifecycle(
    strategy_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> StrategyHealthTimelineResponse:
    """Dashboard timeline of health evidence, decisions, and research follow-up."""
    return StrategyHealthTimelineResponse.model_validate(
        StrategyHealthService(session).timeline(strategy_id)
    )


@router.get("/strategies/compare", response_model=StrategyComparisonResponse)
def compare_strategies(
    champion_id: UUID,
    challenger_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> StrategyComparisonResponse:
    comparison = DashboardService(session).compare_strategies(champion_id, challenger_id)
    if comparison is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="strategy not found")
    return comparison


@router.get("/paper-trading/sessions/{session_id}", response_model=PaperTradingDashboardResponse)
def get_dashboard_paper_session(
    session_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> PaperTradingDashboardResponse:
    detail = DashboardService(session).paper_session(session_id)
    if detail is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    return detail
