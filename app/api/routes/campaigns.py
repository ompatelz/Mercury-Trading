from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.campaigns.schemas import (
    CampaignCreateRequest,
    CampaignExperimentResponse,
    CampaignJobResponse,
    CampaignResponse,
    CampaignRunRequest,
    OptimizationStudyCreateRequest,
    OptimizationStudyResponse,
    OptimizationTrialResponse,
    PortfolioEvaluationResponse,
    QueueStatusResponse,
    StrategyRankingResponse,
    WorkerRunRequest,
    WorkerStatusResponse,
)
from app.campaigns.service import CampaignService
from app.campaigns.study_service import OptimizationStudyService
from app.db.session import get_session
from app.models.campaign import CampaignJob
from app.research_artifacts.service import ResearchArtifactService, artifact_to_dict

router = APIRouter(tags=["campaigns"])


@router.post(
    "/optimization/studies",
    response_model=OptimizationStudyResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_optimization_study(
    request: OptimizationStudyCreateRequest,
    session: Annotated[Session, Depends(get_session)],
) -> OptimizationStudyResponse:
    try:
        study = OptimizationStudyService(session).create(request)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return OptimizationStudyResponse.model_validate(study)


@router.get("/optimization/studies/{study_id}", response_model=OptimizationStudyResponse)
def get_optimization_study(
    study_id: UUID, session: Annotated[Session, Depends(get_session)]
) -> OptimizationStudyResponse:
    study = OptimizationStudyService(session).get(study_id)
    if study is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="optimization study not found"
        )
    return OptimizationStudyResponse.model_validate(study)


@router.get(
    "/optimization/studies/{study_id}/trials", response_model=list[OptimizationTrialResponse]
)
def list_optimization_trials(
    study_id: UUID, session: Annotated[Session, Depends(get_session)]
) -> list[OptimizationTrialResponse]:
    try:
        return [
            OptimizationTrialResponse.model_validate(item)
            for item in OptimizationStudyService(session).list_trials(study_id)
        ]
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/optimization/studies/{study_id}/run", response_model=OptimizationStudyResponse)
def run_optimization_study(
    study_id: UUID, session: Annotated[Session, Depends(get_session)]
) -> OptimizationStudyResponse:
    try:
        study = OptimizationStudyService(session).run(study_id)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return OptimizationStudyResponse.model_validate(study)


@router.post("/optimization/studies/{study_id}/cancel", response_model=OptimizationStudyResponse)
def cancel_optimization_study(
    study_id: UUID, session: Annotated[Session, Depends(get_session)]
) -> OptimizationStudyResponse:
    try:
        study = OptimizationStudyService(session).cancel(study_id)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return OptimizationStudyResponse.model_validate(study)


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
        artifact = ResearchArtifactService(session).campaign_artifact(campaign_id)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {**report, "artifact": artifact_to_dict(artifact)}


@router.get("/jobs/{job_id}", response_model=CampaignJobResponse)
def get_job(job_id: UUID, session: Annotated[Session, Depends(get_session)]) -> CampaignJobResponse:
    job = CampaignService(session).get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return CampaignJobResponse.model_validate(job)


@router.post("/jobs/{job_id}/cancel", response_model=CampaignJobResponse)
def cancel_job(
    job_id: UUID, session: Annotated[Session, Depends(get_session)]
) -> CampaignJobResponse:
    try:
        job = CampaignService(session).cancel_job(job_id)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return CampaignJobResponse.model_validate(job)


@router.get("/queue/status", response_model=QueueStatusResponse)
def queue_status(session: Annotated[Session, Depends(get_session)]) -> QueueStatusResponse:
    rows = session.execute(
        select(CampaignJob.status, func.count()).group_by(CampaignJob.status)
    ).all()
    counts: dict[str, int] = {job_status: count for job_status, count in rows}
    return QueueStatusResponse(
        jobs_queued=counts.get("QUEUED", 0),
        jobs_running=counts.get("RUNNING", 0),
        jobs_succeeded=counts.get("SUCCEEDED", 0),
        jobs_failed=counts.get("FAILED", 0),
        jobs_retrying=counts.get("RETRYING", 0),
        jobs_cancelled=counts.get("CANCELLED", 0),
    )


@router.get("/workers", response_model=list[WorkerStatusResponse])
def workers(session: Annotated[Session, Depends(get_session)]) -> list[WorkerStatusResponse]:
    rows = session.execute(
        select(CampaignJob.worker, func.count(), func.max(CampaignJob.heartbeat_at))
        .where(CampaignJob.worker.is_not(None), CampaignJob.status == "RUNNING")
        .group_by(CampaignJob.worker)
    )
    return [
        WorkerStatusResponse(worker_id=row[0], active_jobs=row[1], last_heartbeat_at=row[2])
        for row in rows
    ]


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
