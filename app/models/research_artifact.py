import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ResearchArtifact(Base):
    __tablename__ = "research_artifacts"
    __table_args__ = (
        UniqueConstraint("artifact_type", "experiment_id", name="uq_artifact_experiment_type"),
        UniqueConstraint("artifact_type", "campaign_id", name="uq_artifact_campaign_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    experiment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("experiments.id", ondelete="CASCADE"), nullable=True
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("research_campaigns.id", ondelete="CASCADE"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    hypothesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    methodology: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    strategy_definition: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    dataset: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    validation_method: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    performance_metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    risk_metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    regime_metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    risk_flags: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    overfitting_flags: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    critic_summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    conclusion: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    measured_results: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    interpretation: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    provenance: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    reproducibility_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    charts: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    export_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    markdown_report: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
