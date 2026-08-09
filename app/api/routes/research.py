from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.agent import ResearchTraceEvent
from app.models.experiment import ResearchExperiment
from app.research.schemas import (
    ResearchExperimentRequest,
    ResearchExperimentResponse,
    ResearchTraceEventResponse,
)
from app.research.service import ResearchExperimentService

router = APIRouter(prefix="/research", tags=["research"])


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
