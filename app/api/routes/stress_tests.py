from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.stress_testing.service import StressTestService

router = APIRouter(tags=["stress-tests"])


class StressTestRequest(BaseModel):
    experiment_id: UUID
    block_size: int = Field(default=5, ge=1)
    number_of_simulations: int = Field(default=200, ge=1, le=10_000)
    seed: int = 17


@router.post("/stress-tests", status_code=status.HTTP_201_CREATED)
def run_stress_test(
    request: StressTestRequest, session: Annotated[Session, Depends(get_session)]
) -> dict[str, Any]:
    try:
        study = StressTestService(session).run(
            request.experiment_id,
            block_size=request.block_size,
            simulations=request.number_of_simulations,
            seed=request.seed,
        )
        session.commit()
        return study
    except ValueError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.get("/stress-tests/{experiment_id}")
@router.get("/experiments/{experiment_id}/stress")
def get_stress_test(
    experiment_id: UUID, session: Annotated[Session, Depends(get_session)]
) -> dict[str, Any]:
    try:
        study = StressTestService(session).get(experiment_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if study is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="stress test not found")
    return study
