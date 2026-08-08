from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_market_data_provider
from app.db.session import get_session
from app.market_data.normalization import MarketDataValidationError
from app.market_data.provider import MarketDataProvider
from app.market_data.service import MarketDataService
from app.schemas.market_data import (
    MarketBarResponse,
    MarketDataIngestRequest,
    MarketDataIngestResponse,
)

router = APIRouter(prefix="/market-data", tags=["market-data"])


@router.post(
    "/ingest",
    response_model=MarketDataIngestResponse,
    status_code=status.HTTP_201_CREATED,
)
def ingest_market_data(
    request: MarketDataIngestRequest,
    session: Annotated[Session, Depends(get_session)],
    provider: Annotated[MarketDataProvider, Depends(get_market_data_provider)],
) -> MarketDataIngestResponse:
    if request.start >= request.end:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="start must be before end"
        )
    service = MarketDataService(session=session, provider=provider)
    try:
        rows_fetched, rows_inserted = service.ingest(
            symbol=request.symbol,
            start=request.start,
            end=request.end,
            interval=request.interval,
        )
        session.commit()
    except MarketDataValidationError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    return MarketDataIngestResponse(
        symbol=request.symbol.upper(),
        interval=request.interval,
        rows_fetched=rows_fetched,
        rows_inserted=rows_inserted,
    )


@router.get("/{symbol}", response_model=list[MarketBarResponse])
def get_market_data(
    symbol: str,
    session: Annotated[Session, Depends(get_session)],
    interval: Annotated[str, Query()] = "1d",
    start: Annotated[date | None, Query()] = None,
    end: Annotated[date | None, Query()] = None,
) -> list[MarketBarResponse]:
    service = MarketDataService(session=session, provider=get_market_data_provider())
    bars = service.list_bars(symbol=symbol, interval=interval, start=start, end=end)
    return [MarketBarResponse.model_validate(bar, from_attributes=True) for bar in bars]
