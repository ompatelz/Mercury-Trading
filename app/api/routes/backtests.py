from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.experiments.repository import ExperimentRepository
from app.experiments.service import ExperimentService
from app.schemas.experiment import BacktestRequest, BacktestTradeResponse, ExperimentResponse

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
    return _get_experiment_response(experiment_id, session)


@router.get("/backtests/{backtest_id}", response_model=ExperimentResponse)
def get_backtest(
    backtest_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> ExperimentResponse:
    return _get_experiment_response(backtest_id, session)


@router.get("/backtests/{backtest_id}/trades", response_model=list[BacktestTradeResponse])
def get_backtest_trades(
    backtest_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> list[BacktestTradeResponse]:
    repository = ExperimentRepository(session)
    if repository.get(backtest_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="backtest not found")
    return [
        BacktestTradeResponse.model_validate(trade) for trade in repository.list_trades(backtest_id)
    ]


def _get_experiment_response(experiment_id: UUID, session: Session) -> ExperimentResponse:
    experiment = ExperimentRepository(session).get(experiment_id)
    if experiment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="experiment not found")
    return ExperimentResponse.model_validate(experiment)
