import asyncio
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.dependencies import get_live_paper_trading_service
from app.db.session import get_session
from app.paper_trading.live_service import LivePaperTradingService
from app.paper_trading.monitoring import ComponentHealth, ComponentStatus, live_update_hub
from app.paper_trading.repository import PaperTradingRepository
from app.paper_trading.schemas import (
    ComponentHealthResponse,
    LivePaperTradingSessionCreateRequest,
    PaperOrderResponse,
    PaperTradingSessionResponse,
)

router = APIRouter(prefix="/live", tags=["live"])


@router.post(
    "/sessions",
    response_model=PaperTradingSessionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_live_session(
    request: LivePaperTradingSessionCreateRequest,
    service: Annotated[LivePaperTradingService, Depends(get_live_paper_trading_service)],
) -> PaperTradingSessionResponse:
    try:
        paper_session = service.create_session(request)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return PaperTradingSessionResponse.model_validate(paper_session)


@router.post("/sessions/{session_id}/stop", response_model=PaperTradingSessionResponse)
def stop_live_session(
    session_id: UUID,
    service: Annotated[LivePaperTradingService, Depends(get_live_paper_trading_service)],
) -> PaperTradingSessionResponse:
    try:
        paper_session = service.stop_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return PaperTradingSessionResponse.model_validate(paper_session)


@router.get("/sessions/{session_id}", response_model=PaperTradingSessionResponse)
def get_live_session(
    session_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> PaperTradingSessionResponse:
    paper_session = PaperTradingRepository(session).get_session(session_id)
    if paper_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    return PaperTradingSessionResponse.model_validate(paper_session)


@router.get("/sessions/{session_id}/portfolio")
def get_live_portfolio(
    session_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    paper_session = PaperTradingRepository(session).get_session(session_id)
    if paper_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    return paper_session.final_portfolio


@router.get("/sessions/{session_id}/orders", response_model=list[PaperOrderResponse])
def list_live_orders(
    session_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> list[PaperOrderResponse]:
    repository = PaperTradingRepository(session)
    if repository.get_session(session_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    return [
        PaperOrderResponse.model_validate(order) for order in repository.list_orders(session_id)
    ]


@router.get("/sessions/{session_id}/metrics")
def get_live_metrics(
    session_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    paper_session = PaperTradingRepository(session).get_session(session_id)
    if paper_session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    return paper_session.metrics


@router.get("/health", response_model=list[ComponentHealthResponse])
def live_health(
    service: Annotated[LivePaperTradingService, Depends(get_live_paper_trading_service)],
    session: Annotated[Session, Depends(get_session)],
) -> list[ComponentHealthResponse]:
    health = service.health()
    try:
        session.execute(text("select 1"))
        health.append(ComponentHealth(component="Database", status=ComponentStatus.HEALTHY))
    except Exception as exc:
        health.append(
            ComponentHealth(
                component="Database",
                status=ComponentStatus.UNHEALTHY,
                reason=str(exc),
            )
        )
    return [
        ComponentHealthResponse(
            component=item.component,
            status=item.status.value,
            reason=item.reason,
        )
        for item in health
    ]


@router.websocket("/sessions/{session_id}/ws")
async def live_session_updates(websocket: WebSocket, session_id: UUID) -> None:
    await websocket.accept()
    cursor = 0
    try:
        while True:
            events = live_update_hub.list_events(session_id, after=cursor)
            cursor += len(events)
            for event in events:
                await websocket.send_json(event)
            await asyncio.sleep(0.25)
    except WebSocketDisconnect:
        return
