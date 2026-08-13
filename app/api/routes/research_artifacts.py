from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.research_artifacts.service import ResearchArtifactService, artifact_to_dict

router = APIRouter(tags=["research-artifacts"])


@router.get("/experiments/{experiment_id}/report", response_model=None)
def get_experiment_report(
    experiment_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    format: Annotated[Literal["json", "markdown"], Query()] = "json",
) -> Any:
    try:
        artifact = ResearchArtifactService(session).experiment_artifact(experiment_id)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if format == "markdown":
        return PlainTextResponse(artifact.markdown_report)
    return artifact_to_dict(artifact)


@router.post("/experiments/{experiment_id}/reproduce")
def reproduce_experiment(
    experiment_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    try:
        return ResearchArtifactService(session).reproduce_experiment(experiment_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/research-artifacts/{artifact_id}", response_model=None)
def get_research_artifact(
    artifact_id: UUID,
    session: Annotated[Session, Depends(get_session)],
    format: Annotated[Literal["json", "markdown"], Query()] = "json",
) -> Any:
    artifact = ResearchArtifactService(session).get_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="artifact not found")
    if format == "markdown":
        return PlainTextResponse(artifact.markdown_report)
    return artifact_to_dict(artifact)
