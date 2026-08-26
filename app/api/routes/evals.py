from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.evals.benchmarks import DEFAULT_BENCHMARK_NAME, DEFAULT_BENCHMARK_VERSION, get_benchmark
from app.evals.schemas import (
    BenchmarkResponse,
    ChampionResponse,
    EvalRunRequest,
    EvalRunResponse,
    EvalTaskResultResponse,
    VersionComparisonRequest,
    VersionComparisonResponse,
    WorkflowExperimentRequest,
    WorkflowExperimentResponse,
)
from app.evals.service import EvalService

router = APIRouter(prefix="/evals", tags=["evals"])


@router.get("/benchmarks", response_model=list[BenchmarkResponse])
def list_benchmarks() -> list[BenchmarkResponse]:
    tasks = get_benchmark(DEFAULT_BENCHMARK_NAME)
    return [
        BenchmarkResponse(
            name=DEFAULT_BENCHMARK_NAME,
            version=DEFAULT_BENCHMARK_VERSION,
            tasks=[
                {
                    "task_id": task.task_id,
                    "task_type": task.task_type,
                    "input": task.input,
                    "expected_constraints": task.expected_constraints,
                    "scoring_rules": list(task.scoring_rules),
                    "fixtures": task.fixtures,
                    "metadata": task.metadata,
                    "critical": task.critical,
                }
                for task in tasks
            ],
        )
    ]


@router.get("/versions")
def list_eval_versions(session: Annotated[Session, Depends(get_session)]) -> dict[str, object]:
    from app.agents.service import AgentVersionService

    service = AgentVersionService(session)
    service.ensure_default_workflow()
    session.commit()
    return {
        "workflows": [
            {
                "id": str(item.id),
                "name": item.name,
                "version": item.version,
                "status": item.status,
                "manifest": item.manifest,
            }
            for item in service.list_workflow_versions()
        ]
    }


@router.post(
    "/workflow-experiments",
    response_model=WorkflowExperimentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_workflow_experiment(
    request: WorkflowExperimentRequest, session: Annotated[Session, Depends(get_session)]
) -> WorkflowExperimentResponse:
    try:
        experiment = EvalService(session).create_workflow_experiment(
            request.baseline_workflow_version_id,
            request.candidate_workflow_version_id,
            request.benchmark_name,
            request.promotion_rules,
        )
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return WorkflowExperimentResponse.model_validate(experiment)


@router.post("/candidates/{candidate_id}/promote", response_model=ChampionResponse)
def promote_candidate(
    candidate_id: UUID, session: Annotated[Session, Depends(get_session)]
) -> ChampionResponse:
    try:
        champion = EvalService(session).promote_candidate(candidate_id)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return ChampionResponse(
        component=champion.component,
        workflow_version_id=champion.workflow_version_id,
        promoted_from_experiment_id=champion.promoted_from_experiment_id,
    )


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


@router.post("/runs", response_model=EvalRunResponse, status_code=status.HTTP_201_CREATED)
def run_eval_plural(
    request: EvalRunRequest, session: Annotated[Session, Depends(get_session)]
) -> EvalRunResponse:
    return run_eval(request, session)


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
