from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.agent import ResearchTraceEvent
from app.models.experiment import ResearchExperiment
from app.research.schemas import (
    ResearchExperimentRequest,
    ResearchExperimentResponse,
    ResearchSourceCreateRequest,
    ResearchSourceResponse,
    ResearchTraceEventResponse,
)
from app.research.service import ResearchExperimentService
from app.research_sources.service import AttachedResearchSource, ResearchSourceService

router = APIRouter(prefix="/research", tags=["research"])


def source_response(item: AttachedResearchSource) -> ResearchSourceResponse:
    return ResearchSourceResponse(
        attachment_id=item.attachment.id,
        source_id=item.source.id,
        title=item.attachment.title,
        original_filename=item.attachment.original_filename,
        content_type=item.source.content_type,
        byte_size=item.source.byte_size,
        sha256=item.source.sha256,
        created_at=item.attachment.created_at,
        deduplicated=item.deduplicated,
    )


@router.post(
    "/experiments",
    response_model=ResearchExperimentResponse,
    status_code=status.HTTP_201_CREATED,
)
def run_research_experiment(
    request: ResearchExperimentRequest,
    session: Annotated[Session, Depends(get_session)],
) -> ResearchExperimentResponse:
    service = ResearchExperimentService(session=session)
    try:
        experiment = service.run_research_experiment(request)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return ResearchExperimentResponse.model_validate(experiment)


@router.get("/experiments", response_model=list[ResearchExperimentResponse])
def list_research_experiments(
    session: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=50)] = 12,
) -> list[ResearchExperimentResponse]:
    """Return recent, persisted research sessions for the research desk."""
    experiments = session.scalars(
        select(ResearchExperiment).order_by(ResearchExperiment.created_at.desc()).limit(limit)
    )
    return [ResearchExperimentResponse.model_validate(experiment) for experiment in experiments]


@router.post(
    "/experiments/{experiment_id}/sources",
    response_model=ResearchSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
def attach_research_source(
    experiment_id: UUID,
    request: ResearchSourceCreateRequest,
    session: Annotated[Session, Depends(get_session)],
) -> ResearchSourceResponse:
    try:
        item = ResearchSourceService(session).attach(experiment_id, request)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return source_response(item)


@router.get("/experiments/{experiment_id}/sources", response_model=list[ResearchSourceResponse])
def list_research_sources(
    experiment_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> list[ResearchSourceResponse]:
    try:
        items = ResearchSourceService(session).list_for_experiment(experiment_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [source_response(item) for item in items]


@router.get("/experiments/{experiment_id}", response_model=ResearchExperimentResponse)
def get_research_experiment(
    experiment_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> ResearchExperimentResponse:
    experiment = session.get(ResearchExperiment, experiment_id)
    if experiment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="research experiment not found"
        )
    return ResearchExperimentResponse.model_validate(experiment)


@router.get("/experiments/{experiment_id}/trace", response_model=list[ResearchTraceEventResponse])
def get_research_trace(
    experiment_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> list[ResearchTraceEventResponse]:
    if session.get(ResearchExperiment, experiment_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="research experiment not found"
        )
    events = session.scalars(
        select(ResearchTraceEvent)
        .where(ResearchTraceEvent.research_experiment_id == experiment_id)
        .order_by(ResearchTraceEvent.id)
    )
    return [ResearchTraceEventResponse.model_validate(event) for event in events]
