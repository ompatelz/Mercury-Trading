from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.campaigns.schemas import (
    CampaignCreateRequest,
    CampaignExperimentResponse,
    CampaignJobResponse,
    CampaignResponse,
    CampaignRunRequest,
    PortfolioEvaluationResponse,
    StrategyRankingResponse,
    WorkerRunRequest,
)
from app.campaigns.service import CampaignService
from app.db.session import get_session

router = APIRouter(tags=["campaigns"])


@router.post("/campaigns", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
def create_campaign(
    request: CampaignCreateRequest,
    session: Annotated[Session, Depends(get_session)],
) -> CampaignResponse:
    try:
        campaign = CampaignService(session).create_campaign(request)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return CampaignResponse.model_validate(campaign)


@router.get("/campaigns", response_model=list[CampaignResponse])
def list_campaigns(session: Annotated[Session, Depends(get_session)]) -> list[CampaignResponse]:
    campaigns = CampaignService(session).list_campaigns()
    return [CampaignResponse.model_validate(item) for item in campaigns]


@router.get("/campaigns/{campaign_id}", response_model=CampaignResponse)
def get_campaign(
    campaign_id: UUID, session: Annotated[Session, Depends(get_session)]
) -> CampaignResponse:
    campaign = CampaignService(session).get_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="campaign not found")
    return CampaignResponse.model_validate(campaign)


@router.post("/campaigns/{campaign_id}/run", response_model=list[CampaignJobResponse])
def run_campaign(
    campaign_id: UUID,
    request: CampaignRunRequest,
    session: Annotated[Session, Depends(get_session)],
) -> list[CampaignJobResponse]:
    try:
        jobs = CampaignService(session).run_campaign(campaign_id, request.batch_size)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return [CampaignJobResponse.model_validate(job) for job in jobs]


@router.post("/campaigns/{campaign_id}/cancel", response_model=CampaignResponse)
def cancel_campaign(
    campaign_id: UUID, session: Annotated[Session, Depends(get_session)]
) -> CampaignResponse:
    try:
        campaign = CampaignService(session).cancel_campaign(campaign_id)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return CampaignResponse.model_validate(campaign)


@router.get("/campaigns/{campaign_id}/experiments", response_model=list[CampaignExperimentResponse])
def list_campaign_experiments(
    campaign_id: UUID, session: Annotated[Session, Depends(get_session)]
) -> list[CampaignExperimentResponse]:
    return [
        CampaignExperimentResponse.model_validate(item)
        for item in CampaignService(session).list_experiments(campaign_id)
    ]


@router.get("/campaigns/{campaign_id}/jobs", response_model=list[CampaignJobResponse])
def list_campaign_jobs(
    campaign_id: UUID, session: Annotated[Session, Depends(get_session)]
) -> list[CampaignJobResponse]:
    return [
        CampaignJobResponse.model_validate(item)
        for item in CampaignService(session).list_jobs(campaign_id)
    ]


@router.get("/campaigns/{campaign_id}/rankings", response_model=list[StrategyRankingResponse])
def list_campaign_rankings(
    campaign_id: UUID, session: Annotated[Session, Depends(get_session)]
) -> list[StrategyRankingResponse]:
    return [
        StrategyRankingResponse.model_validate(item)
        for item in CampaignService(session).list_rankings(campaign_id)
    ]


@router.get("/campaigns/{campaign_id}/portfolios", response_model=list[PortfolioEvaluationResponse])
def list_campaign_portfolios(
    campaign_id: UUID, session: Annotated[Session, Depends(get_session)]
) -> list[PortfolioEvaluationResponse]:
    return [
        PortfolioEvaluationResponse.model_validate(item)
        for item in CampaignService(session).list_portfolios(campaign_id)
    ]


@router.get("/campaigns/{campaign_id}/report")
def get_campaign_report(
    campaign_id: UUID, session: Annotated[Session, Depends(get_session)]
) -> dict[str, object]:
    try:
        report = CampaignService(session).get_report(campaign_id)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return report


@router.get("/jobs/{job_id}", response_model=CampaignJobResponse)
def get_job(job_id: UUID, session: Annotated[Session, Depends(get_session)]) -> CampaignJobResponse:
    job = CampaignService(session).get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return CampaignJobResponse.model_validate(job)


@router.post("/jobs/work", response_model=list[CampaignJobResponse])
def process_jobs(
    request: WorkerRunRequest,
    session: Annotated[Session, Depends(get_session)],
) -> list[CampaignJobResponse]:
    service = CampaignService(session)
    processed = []
    for _ in range(request.max_jobs):
        try:
            job = service.process_next_job(request.worker_name)
            session.commit()
        except Exception as exc:
            session.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
            ) from exc
        if job is None:
            break
        processed.append(job)
    return [CampaignJobResponse.model_validate(job) for job in processed]
