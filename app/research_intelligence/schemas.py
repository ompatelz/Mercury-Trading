from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class HypothesisProposal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    claim: str = Field(min_length=10)
    intuition: str = Field(min_length=10)
    required_data: tuple[str, ...] = Field(min_length=1)
    strategy_family: str = Field(min_length=1)
    expected_regime: str = Field(min_length=1)
    holding_period: str = Field(min_length=1)
    falsification_criteria: tuple[str, ...] = Field(min_length=1)
    major_risks: tuple[str, ...] = Field(min_length=1)
    expected_research_cost: float = Field(ge=0)


class TriageResult(BaseModel):
    accepted: bool
    priority: float
    rejection_reasons: list[str]
    similar_hypotheses: list[str]
    negative_memory: list[str]
    score_components: dict[str, float]
