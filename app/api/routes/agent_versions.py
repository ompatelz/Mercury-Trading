from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.schemas import AgentVersionResponse, WorkflowVersionResponse
from app.agents.service import AgentVersionService
from app.db.session import get_session
from app.evals.schemas import EvalRunRequest, EvalRunResponse
from app.evals.service import EvalService
from app.models.agent import AgentVersion, WorkflowVersion

router = APIRouter(tags=["agent-versions"])


@router.get("/agent-versions", response_model=list[AgentVersionResponse])
def list_agent_versions(
    session: Annotated[Session, Depends(get_session)],
) -> list[AgentVersionResponse]:
    service = AgentVersionService(session)
    service.ensure_default_agent()
    session.commit()
    return [AgentVersionResponse.model_validate(record) for record in service.list_agent_versions()]


@router.get("/workflow-versions", response_model=list[WorkflowVersionResponse])
def list_workflow_versions(
    session: Annotated[Session, Depends(get_session)],
) -> list[WorkflowVersionResponse]:
    service = AgentVersionService(session)
    service.ensure_default_workflow()
    session.commit()
    return [
        WorkflowVersionResponse.model_validate(record)
        for record in service.list_workflow_versions()
    ]


@router.get("/agent-versions/{agent_version_id}", response_model=AgentVersionResponse)
def get_agent_version(
    agent_version_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> AgentVersionResponse:
    record = session.get(AgentVersion, agent_version_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent version not found")
    return AgentVersionResponse.model_validate(record)


@router.get("/workflow-versions/{workflow_version_id}", response_model=WorkflowVersionResponse)
def get_workflow_version(
    workflow_version_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> WorkflowVersionResponse:
    record = session.get(WorkflowVersion, workflow_version_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="workflow version not found"
        )
    return WorkflowVersionResponse.model_validate(record)


@router.post(
    "/agent-versions/{agent_version_id}/evaluate",
    response_model=EvalRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def evaluate_agent_version(
    agent_version_id: UUID,
    request: EvalRunRequest,
    session: Annotated[Session, Depends(get_session)],
) -> EvalRunResponse:
    agent = session.get(AgentVersion, agent_version_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent version not found")
    service = EvalService(session)
    run = service.run_benchmark(
        benchmark_name=request.benchmark_name,
        workflow_version_id=request.workflow_version_id,
    )
    session.commit()
    return EvalRunResponse.model_validate(run)
