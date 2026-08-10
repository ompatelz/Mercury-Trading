from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.evolution.schemas import (
    EvolutionRunCreateRequest,
    EvolutionRunResponse,
    StrategyCandidateResponse,
)
from app.evolution.service import EvolutionService

router = APIRouter(tags=["evolution"])


@router.post(
    "/evolution-runs",
    response_model=EvolutionRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_evolution_run(
    request: EvolutionRunCreateRequest,
    session: Annotated[Session, Depends(get_session)],
) -> EvolutionRunResponse:
    try:
        run = EvolutionService(session).create_run(request)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return EvolutionRunResponse.model_validate(run)


@router.get("/evolution-runs/{run_id}", response_model=EvolutionRunResponse)
def get_evolution_run(
    run_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> EvolutionRunResponse:
    run = EvolutionService(session).get_run(run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="evolution run not found")
    return EvolutionRunResponse.model_validate(run)


@router.get("/evolution-runs/{run_id}/population", response_model=list[StrategyCandidateResponse])
def get_population(
    run_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> list[StrategyCandidateResponse]:
    return [
        StrategyCandidateResponse.model_validate(candidate)
        for candidate in EvolutionService(session).list_candidates(run_id)
    ]


@router.get("/evolution-runs/{run_id}/champion", response_model=StrategyCandidateResponse)
def get_champion(
    run_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> StrategyCandidateResponse:
    champion = EvolutionService(session).champion(run_id)
    if champion is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="champion not found")
    return StrategyCandidateResponse.model_validate(champion)


@router.post("/evolution-runs/memory-comparison")
def compare_memory_conditioning(
    request: EvolutionRunCreateRequest,
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    result = EvolutionService(session).memory_comparison(request)
    session.commit()
    return result
