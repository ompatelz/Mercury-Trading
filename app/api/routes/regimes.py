from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.regimes.engine import REGIME_VERSION
from app.regimes.schemas import RegimeComputeRequest, RegimeLabelResponse
from app.regimes.service import RegimeService

router = APIRouter(tags=["regimes"])


@router.post(
    "/regimes", response_model=list[RegimeLabelResponse], status_code=status.HTTP_201_CREATED
)
def compute_regimes(
    request: RegimeComputeRequest,
    session: Annotated[Session, Depends(get_session)],
) -> list[RegimeLabelResponse]:
    labels = RegimeService(session).compute_and_persist(
        request.symbol,
        interval=request.interval,
        start=request.start,
        end=request.end,
        lookback=request.lookback,
        regime_version=request.regime_version,
    )
    session.commit()
    return [RegimeLabelResponse.model_validate(label) for label in labels]


@router.get("/regimes", response_model=list[RegimeLabelResponse])
def list_regimes(
    session: Annotated[Session, Depends(get_session)],
    symbol: str | None = None,
    interval: str = "1d",
    regime_version: str = REGIME_VERSION,
) -> list[RegimeLabelResponse]:
    labels = RegimeService(session).list_labels(
        symbol=symbol, interval=interval, regime_version=regime_version
    )
    return [RegimeLabelResponse.model_validate(label) for label in labels]


@router.get("/regimes/{symbol}", response_model=list[RegimeLabelResponse])
def list_symbol_regimes(
    symbol: str,
    session: Annotated[Session, Depends(get_session)],
    interval: str = "1d",
    regime_version: str = REGIME_VERSION,
) -> list[RegimeLabelResponse]:
    labels = RegimeService(session).list_labels(
        symbol=symbol, interval=interval, regime_version=regime_version
    )
    return [RegimeLabelResponse.model_validate(label) for label in labels]


@router.get("/regimes/{symbol}/transitions")
def regime_transitions(
    symbol: str,
    session: Annotated[Session, Depends(get_session)],
    interval: str = "1d",
    regime_version: str = REGIME_VERSION,
) -> list[dict[str, object]]:
    return RegimeService(session).transitions(
        symbol=symbol, interval=interval, regime_version=regime_version
    )


@router.get("/strategies/{strategy_id}/regime-performance")
def strategy_regime_performance(
    strategy_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    try:
        return RegimeService(session).experiment_regime_performance(strategy_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
