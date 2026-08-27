from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.strategy_dsl.schemas import StrategySpec


class StrategyValidationResponse(BaseModel):
    valid: bool
    errors: list[str]
    strategy_hash: str | None = None
    complexity: int | None = None
    plan: list[str] = []


class StrategyResponse(BaseModel):
    id: UUID
    strategy_hash: str
    dsl_version: str
    compiler_version: str
    spec: StrategySpec
    complexity: int
    explanation: str
    created_at: datetime

    model_config = {"from_attributes": True}
