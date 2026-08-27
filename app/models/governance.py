import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DecisionRecord(Base):
    """Append-only explanation of a durable research decision."""

    __tablename__ = "decision_records"
    __table_args__ = (
        Index("ix_decisions_campaign_created", "campaign_id", "created_at"),
        Index("ix_decisions_strategy_created", "strategy_id", "created_at"),
        Index("ix_decisions_type_created", "decision_type", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    decision_type: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    experiment_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    workflow_experiment_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    alternatives: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    versions: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("decision_records.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DecisionRuleEvaluation(Base):
    __tablename__ = "decision_rule_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    decision_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("decision_records.id", ondelete="CASCADE"), nullable=False
    )
    rule: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(32), nullable=False)
    threshold: Mapped[Any] = mapped_column(JSON, nullable=False)
    observed_value: Mapped[Any] = mapped_column(JSON, nullable=False)
    passed: Mapped[bool] = mapped_column(nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
