from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.ml_research.api_schemas import MLRunRequest
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
