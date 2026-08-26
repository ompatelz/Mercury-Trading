import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ResearchCampaign(Base):
    __tablename__ = "research_campaigns"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    constraints: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    datasets: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    symbols: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    interval: Mapped[str] = mapped_column(String(16), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    split_definition: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    budget: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    budget_used: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    generated_hypotheses: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    candidate_strategies: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    rejected_strategies: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    final_conclusions: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    stop_conditions: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    jobs: Mapped[list["CampaignJob"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )
    experiments: Mapped[list["CampaignExperiment"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )
    rankings: Mapped[list["StrategyRanking"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )
    portfolios: Mapped[list["PortfolioEvaluation"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )


class CampaignExperiment(Base):
    __tablename__ = "campaign_experiments"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id", "idempotency_key", name="uq_campaign_experiments_idempotency"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_campaigns.id", ondelete="CASCADE"), nullable=False
    )
    experiment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("experiments.id", ondelete="SET NULL"), nullable=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    hypothesis: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    strategy_family: Mapped[str] = mapped_column(String(100), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    split_role: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    evaluation: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    risk_flags: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    campaign: Mapped[ResearchCampaign] = relationship(back_populates="experiments")


class CampaignJob(Base):
    __tablename__ = "campaign_jobs"
    __table_args__ = (
        UniqueConstraint("campaign_id", "idempotency_key", name="uq_campaign_jobs_idempotency"),
        Index("ix_campaign_jobs_status_available_priority", "status", "available_at", "priority"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_campaigns.id", ondelete="CASCADE"), nullable=False
    )
    campaign_experiment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("campaign_experiments.id", ondelete="SET NULL"), nullable=True
    )
    experiment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("experiments.id", ondelete="SET NULL"), nullable=True
    )
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    payload_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    worker: Mapped[str | None] = mapped_column(String(128), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    attempt_count: Mapped[int] = mapped_column(default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(default=3, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    retry_history: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    error_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    runtime_ms: Mapped[float | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    campaign: Mapped[ResearchCampaign] = relationship(back_populates="jobs")


class StrategyRanking(Base):
    __tablename__ = "strategy_rankings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_campaigns.id", ondelete="CASCADE"), nullable=False
    )
    campaign_experiment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaign_experiments.id", ondelete="CASCADE"), nullable=False
    )
    score: Mapped[float] = mapped_column(nullable=False)
    component_scores: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    ranking_reason: Mapped[str] = mapped_column(Text, nullable=False)
    risk_flags: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    rank: Mapped[int] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    campaign: Mapped[ResearchCampaign] = relationship(back_populates="rankings")


class PortfolioEvaluation(Base):
    __tablename__ = "portfolio_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_campaigns.id", ondelete="CASCADE"), nullable=False
    )
    strategy_experiment_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    weighting_method: Mapped[str] = mapped_column(String(64), nullable=False)
    weights: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    diversification_benefit: Mapped[float] = mapped_column(nullable=False)
    correlation_matrix: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    campaign: Mapped[ResearchCampaign] = relationship(back_populates="portfolios")
