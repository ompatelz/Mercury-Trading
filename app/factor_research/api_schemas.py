from pydantic import BaseModel, Field

from app.factor_research.schemas import FactorStrategySpec, ForwardReturn, ScorePoint


class FactorEvaluationRequest(BaseModel):
    strategy: FactorStrategySpec
    scores: dict[str, list[ScorePoint]] = Field(min_length=1)
    forward_returns: list[ForwardReturn]
