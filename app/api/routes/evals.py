from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.evals.schemas import (
    EvalRunRequest,
    EvalRunResponse,
    EvalTaskResultResponse,
    VersionComparisonRequest,
    VersionComparisonResponse,
)
from app.evals.service import EvalService

router = APIRouter(prefix="/evals", tags=["evals"])


@router.get("", response_model=list[EvalRunResponse])
def list_eval_runs(
    session: Annotated[Session, Depends(get_session)],
) -> list[EvalRunResponse]:
    return [EvalRunResponse.model_validate(run) for run in EvalService(session).list_eval_runs()]


@router.post("/run", response_model=EvalRunResponse, status_code=status.HTTP_201_CREATED)
def run_eval(
    request: EvalRunRequest,
    session: Annotated[Session, Depends(get_session)],
) -> EvalRunResponse:
    service = EvalService(session)
    try:
        run = service.run_benchmark(
            benchmark_name=request.benchmark_name,
            workflow_version_id=request.workflow_version_id,
        )
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return EvalRunResponse.model_validate(run)


@router.get("/{eval_run_id}", response_model=EvalRunResponse)
def get_eval_run(
    eval_run_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> EvalRunResponse:
    run = EvalService(session).get_eval_run(eval_run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="eval run not found")
    return EvalRunResponse.model_validate(run)


@router.get("/{eval_run_id}/tasks", response_model=list[EvalTaskResultResponse])
def get_eval_tasks(
    eval_run_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> list[EvalTaskResultResponse]:
    service = EvalService(session)
    if service.get_eval_run(eval_run_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="eval run not found")
    return [
        EvalTaskResultResponse.model_validate(result)
        for result in service.list_task_results(eval_run_id)
    ]


@router.post(
    "/compare",
    response_model=VersionComparisonResponse,
    status_code=status.HTTP_201_CREATED,
)
def compare_eval_runs(
    request: VersionComparisonRequest,
    session: Annotated[Session, Depends(get_session)],
) -> VersionComparisonResponse:
    service = EvalService(session)
    try:
        comparison = service.compare_runs(
            baseline_eval_run_id=request.baseline_eval_run_id,
            candidate_eval_run_id=request.candidate_eval_run_id,
            min_task_success_delta=request.min_task_success_delta,
            max_latency_increase_pct=request.max_latency_increase_pct,
        )
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return VersionComparisonResponse.model_validate(comparison)
