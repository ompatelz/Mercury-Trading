from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class DecisionRuleResponse(BaseModel):
    rule: str
    rule_version: str
    threshold: Any
    observed_value: Any
    passed: bool
    detail: str | None = None


class DecisionResponse(BaseModel):
    id: UUID
    decision_type: str
    outcome: str
    actor: str
    reason: str
    campaign_id: UUID | None = None
    experiment_id: UUID | None = None
    strategy_id: UUID | None = None
    workflow_experiment_id: UUID | None = None
    correlation_id: str
    inputs: dict[str, Any]
    metrics: dict[str, Any]
    alternatives: list[dict[str, Any]]
    provenance: dict[str, Any]
    versions: dict[str, Any]
    content_hash: str
    supersedes_id: UUID | None = None
    created_at: datetime
    rules: list[DecisionRuleResponse] = Field(default_factory=list)
    integrity: dict[str, Any] = Field(default_factory=dict)
