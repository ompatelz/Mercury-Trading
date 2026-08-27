import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MLModel(Base):
    """Registry metadata only; serialized artifacts remain in object/local storage."""

    __tablename__ = "ml_models"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    model_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    algorithm: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="CANDIDATE")
    dataset_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("dataset_versions.id", ondelete="RESTRICT"), nullable=True
    )
    dataset_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    feature_versions: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    definition: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    artifact_location: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MLPrediction(Base):
    __tablename__ = "ml_predictions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    model_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ml_models.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    asset_id: Mapped[str] = mapped_column(String(64), nullable=False)
    prediction: Mapped[float] = mapped_column(nullable=False)
    score: Mapped[float] = mapped_column(nullable=False)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    feature_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
