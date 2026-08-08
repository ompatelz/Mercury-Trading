from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.experiments.repository import ExperimentRepository
from app.experiments.service import ExperimentService
from app.schemas.experiment import BacktestRequest, ExperimentResponse

router = APIRouter(tags=["experiments"])


@router.post("/backtests", response_model=ExperimentResponse, status_code=status.HTTP_201_CREATED)
def run_backtest(
    request: BacktestRequest,
    session: Annotated[Session, Depends(get_session)],
) -> ExperimentResponse:
    service = ExperimentService(session=session)
    try:
        experiment = service.run_backtest(request)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return ExperimentResponse.model_validate(experiment)


@router.get("/experiments/{experiment_id}", response_model=ExperimentResponse)
def get_experiment(
    experiment_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> ExperimentResponse:
    experiment = ExperimentRepository(session).get(experiment_id)
    if experiment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="experiment not found")
    return ExperimentResponse.model_validate(experiment)
