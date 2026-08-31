from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.paper_trading.repository import PaperTradingRepository
from app.paper_trading.schemas import (
    PaperFillResponse,
    PaperOrderResponse,
    PaperTradingSessionCreateRequest,
    PaperTradingSessionResponse,
)
from app.paper_trading.service import PaperTradingService

router = APIRouter(prefix="/paper-trading", tags=["paper-trading"])


@router.post(
    "/sessions",
    response_model=PaperTradingSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_paper_trading_session(
    request: PaperTradingSessionCreateRequest,
    session: Annotated[Session, Depends(get_session)],
) -> PaperTradingSessionResponse:
    try:
        paper_session = PaperTradingService(session).create_session(request)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return PaperTradingSessionResponse.model_validate(paper_session)


@router.get("/sessions", response_model=list[PaperTradingSessionResponse])
def list_paper_trading_sessions(
    session: Annotated[Session, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=25)] = 8,
) -> list[PaperTradingSessionResponse]:
    return [
        PaperTradingSessionResponse.model_validate(item)
        for item in PaperTradingRepository(session).list_sessions(limit=limit)
    ]


@router.get("/sessions/{session_id}", response_model=PaperTradingSessionResponse)
def get_paper_trading_session(
    session_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> PaperTradingSessionResponse:
    paper_session = PaperTradingRepository(session).get_session(session_id)
    if paper_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    return PaperTradingSessionResponse.model_validate(paper_session)


@router.get("/sessions/{session_id}/orders", response_model=list[PaperOrderResponse])
def list_paper_orders(
    session_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> list[PaperOrderResponse]:
    repository = PaperTradingRepository(session)
    if repository.get_session(session_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    return [
        PaperOrderResponse.model_validate(order) for order in repository.list_orders(session_id)
    ]


@router.get("/sessions/{session_id}/trades", response_model=list[PaperFillResponse])
def list_paper_trades(
    session_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> list[PaperFillResponse]:
    repository = PaperTradingRepository(session)
    if repository.get_session(session_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    return [PaperFillResponse.model_validate(fill) for fill in repository.list_fills(session_id)]


@router.get("/sessions/{session_id}/portfolio")
def get_paper_portfolio(
    session_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    paper_session = PaperTradingRepository(session).get_session(session_id)
    if paper_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    return paper_session.final_portfolio
