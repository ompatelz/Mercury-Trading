from fastapi import APIRouter, HTTPException, status

from app.factor_research.api_schemas import FactorEvaluationRequest
from app.factor_research.compiler import compile_factor_strategy
from app.factor_research.service import FactorResearchService

router = APIRouter(prefix="/factor-research", tags=["factor-research"])


@router.post("/validate")
def validate(request: FactorEvaluationRequest) -> dict[str, object]:
    plan = compile_factor_strategy(request.strategy)
    return {"valid": True, "strategy_hash": plan.strategy_hash, "plan": list(plan.steps)}


@router.post("/evaluate")
def evaluate(request: FactorEvaluationRequest) -> dict[str, object]:
    try:
        return FactorResearchService().evaluate(
            request.strategy, request.scores, request.forward_returns
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
