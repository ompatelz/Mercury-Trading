from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class MemorySearchRequest(BaseModel):
    query: str = Field(min_length=3, max_length=1000)
    symbol: str | None = Field(default=None, max_length=32)
    strategy_family: str | None = Field(default=None, max_length=100)
    market_regime: str | None = Field(default=None, max_length=100)
    failure_type: str | None = Field(default=None, max_length=64)
    top_k: int = Field(default=3, ge=1, le=10)


class MemoryLessonResponse(BaseModel):
    id: UUID
    research_experiment_id: UUID
    backtest_experiment_id: UUID | None
    hypothesis: str
    strategy_family: str
    symbol: str
    asset_class: str
    market_regime: str
    metrics: dict[str, Any]
    risk_flags: list[str]
    failure_reasons: list[str]
    critic_summary: str
    observations: list[str]
    confidence: float
    tags: list[str]
    agent_version: str
    workflow_version: str
    failure_type: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MemorySearchResult(BaseModel):
    lesson: MemoryLessonResponse
    similarity: float
    source_experiment_id: UUID
