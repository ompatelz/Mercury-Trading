from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.strategy_health.schemas import (
    HealthObservationRequest,
    HealthState,
    ResearchScheduleRequest,
    StrategyHealthResponse,
    StrategyHealthTimelineResponse,
)
from app.strategy_health.service import StrategyHealthService

router = APIRouter(prefix="/strategy-health", tags=["strategy-health"])


@router.post("/strategies/{strategy_id}/observations", response_model=StrategyHealthResponse)
def record_observation(
    strategy_id: UUID,
    request: HealthObservationRequest,
    session: Annotated[Session, Depends(get_session)],
) -> StrategyHealthResponse:
    try:
        health = StrategyHealthService(session).record_observation(strategy_id, request)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return StrategyHealthResponse.model_validate(health)


@router.post("/strategies/{strategy_id}/state/{target}", response_model=StrategyHealthResponse)
def transition_state(
    strategy_id: UUID,
    target: HealthState,
    reason: str,
    session: Annotated[Session, Depends(get_session)],
) -> StrategyHealthResponse:
    try:
        health = StrategyHealthService(session).transition(strategy_id, target, reason)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return StrategyHealthResponse.model_validate(health)


@router.get("/strategies/{strategy_id}/timeline", response_model=StrategyHealthTimelineResponse)
def timeline(
    strategy_id: UUID, session: Annotated[Session, Depends(get_session)]
) -> StrategyHealthTimelineResponse:
    return StrategyHealthTimelineResponse.model_validate(
        StrategyHealthService(session).timeline(strategy_id)
    )


@router.post("/schedules", status_code=status.HTTP_201_CREATED)
def create_schedule(
    request: ResearchScheduleRequest, session: Annotated[Session, Depends(get_session)]
) -> dict[str, object]:
    schedule = StrategyHealthService(session).create_schedule(request.model_dump())
    session.commit()
    return {"id": str(schedule.id), "status": schedule.status, "mode": schedule.mode}


@router.post("/schedules/run")
def run_schedules(session: Annotated[Session, Depends(get_session)]) -> list[dict[str, object]]:
    triggers = StrategyHealthService(session).run_due_schedules()
    session.commit()
    return [
        {"id": str(item.id), "status": item.status, "campaign_id": str(item.campaign_id)}
        for item in triggers
    ]
