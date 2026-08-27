from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.models.strategy_dsl import StrategyRecord
from app.strategy_dsl.api_schemas import StrategyResponse, StrategyValidationResponse
from app.strategy_dsl.compiler import compile_strategy
from app.strategy_dsl.schemas import StrategySpec
from app.strategy_dsl.service import StrategyService
from app.strategy_dsl.validation import StrategyValidationError, validate_strategy

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.post("/validate", response_model=StrategyValidationResponse)
def validate(request: StrategySpec) -> StrategyValidationResponse:
    try:
        validate_strategy(request)
        plan = compile_strategy(request)
    except StrategyValidationError as exc:
        return StrategyValidationResponse(valid=False, errors=list(exc.errors))
    return StrategyValidationResponse(
        valid=True,
        errors=[],
        strategy_hash=plan.strategy_hash,
        complexity=plan.complexity,
        plan=list(plan.steps),
    )


@router.post("", response_model=StrategyResponse, status_code=status.HTTP_201_CREATED)
def create(
    request: StrategySpec, session: Annotated[Session, Depends(get_session)]
) -> StrategyResponse:
    try:
        record = StrategyService(session).create(request)
        session.commit()
    except StrategyValidationError as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=list(exc.errors)
        ) from exc
    return StrategyResponse.model_validate(record)


@router.get("/{strategy_id}", response_model=StrategyResponse)
def get(strategy_id: UUID, session: Annotated[Session, Depends(get_session)]) -> StrategyResponse:
    record = session.get(StrategyRecord, strategy_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="strategy not found")
    return StrategyResponse.model_validate(record)


@router.get("/{strategy_id}/explain")
def explain(strategy_id: UUID, session: Annotated[Session, Depends(get_session)]) -> dict[str, str]:
    record = session.get(StrategyRecord, strategy_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="strategy not found")
    return {"explanation": record.explanation, "strategy_hash": record.strategy_hash}
