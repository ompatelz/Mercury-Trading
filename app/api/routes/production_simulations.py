from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.production_simulation import ProductionSimulation
from app.production_simulation.schemas import (
    ProductionSimulationCreateRequest,
    ProductionSimulationResponse,
)
from app.production_simulation.service import ProductionSimulationService

router = APIRouter(prefix="/simulations", tags=["production-simulation"])


def _get(simulation_id: UUID, session: Session) -> ProductionSimulation:
    result = ProductionSimulationService(session).get(simulation_id)
    if result is None:
        raise HTTPException(status_code=404, detail="simulation not found")
    return result


@router.post("", response_model=ProductionSimulationResponse, status_code=status.HTTP_201_CREATED)
def create_simulation(
    request: ProductionSimulationCreateRequest,
    session: Annotated[Session, Depends(get_session)],
) -> ProductionSimulationResponse:
    try:
        result = ProductionSimulationService(session).create_and_run(request)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ProductionSimulationResponse.model_validate(result)


@router.get("/{simulation_id}", response_model=ProductionSimulationResponse)
def get_simulation(
    simulation_id: UUID, session: Annotated[Session, Depends(get_session)]
) -> ProductionSimulationResponse:
    return ProductionSimulationResponse.model_validate(_get(simulation_id, session))


@router.get("/{simulation_id}/timeline")
def timeline(
    simulation_id: UUID, session: Annotated[Session, Depends(get_session)]
) -> list[dict[str, Any]]:
    return _get(simulation_id, session).timeline


@router.get("/{simulation_id}/deployments")
def deployments(
    simulation_id: UUID, session: Annotated[Session, Depends(get_session)]
) -> list[dict[str, Any]]:
    return _get(simulation_id, session).timeline


@router.get("/{simulation_id}/metrics")
def metrics(
    simulation_id: UUID, session: Annotated[Session, Depends(get_session)]
) -> dict[str, Any]:
    return _get(simulation_id, session).metrics
