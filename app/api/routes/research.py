from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.research.schemas import ResearchExperimentRequest, ResearchExperimentResponse
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
