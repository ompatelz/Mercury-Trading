from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.ml_research.api_schemas import (
    MLDriftRequest,
    MLPromotionRequest,
    MLRetrainRequest,
    MLRunRequest,
)
from app.ml_research.lifecycle import MLModelLifecycleService
from app.ml_research.service import MLResearchService

router = APIRouter(prefix="/ml-research", tags=["ml-research"])


@router.post("/evaluate")
def evaluate(
    request: MLRunRequest,
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    try:
        service = MLResearchService()
        result = service.run(request.definition, request.observations)
        model = service.persist(session, request.definition, result)
        session.commit()
        return {**result, "model_id": str(model.id), "model_status": model.status}
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post("/models/{model_id}/drift")
def record_drift(
    model_id: UUID,
    request: MLDriftRequest,
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    try:
        observation = MLModelLifecycleService(session).record_drift(
            model_id,
            observed_at=request.observed_at,
            window_start=request.window_start,
            window_end=request.window_end,
            sample_count=request.sample_count,
            source=request.source,
            baseline=request.baseline,
            observed=request.observed,
        )
        session.commit()
        return {
            "model_id": str(model_id),
            "drift_types": observation.drift_types,
            "consecutive_windows": observation.consecutive_windows,
            "retraining_triggered": observation.retraining_triggered,
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.post("/models/{model_id}/retrain")
def retrain(
    model_id: UUID,
    request: MLRetrainRequest,
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    try:
        candidate = MLModelLifecycleService(session).retrain(
            model_id, request.definition, request.observations, request.trigger
        )
        session.commit()
        return {
            "candidate_model_id": str(candidate.id),
            "candidate_status": candidate.status,
            "deployment_state": candidate.lifecycle_metadata["deployment_state"],
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.post("/models/{candidate_model_id}/promotion")
def decide_promotion(
    candidate_model_id: UUID,
    request: MLPromotionRequest,
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    try:
        promotion = MLModelLifecycleService(session).decide_promotion(
            request.champion_model_id,
            candidate_model_id,
            request.model_dump(mode="json", exclude={"champion_model_id"}),
        )
        session.commit()
        return {
            "decision": promotion.decision,
            "reason": promotion.reason,
            "promotion_id": str(promotion.id),
        }
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.get("/models/{model_id}/lineage")
def lineage(
    model_id: UUID,
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, object]:
    try:
        return MLModelLifecycleService(session).lineage(model_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
