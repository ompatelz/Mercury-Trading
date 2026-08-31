import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ResearchSource(Base):
    """Immutable, user-supplied text kept outside of research execution inputs."""

    __tablename__ = "research_sources"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ResearchSourceAttachment(Base):
    """Immutable provenance link created only after a research experiment exists."""

    __tablename__ = "research_source_attachments"
    __table_args__ = (
        UniqueConstraint(
            "research_experiment_id", "research_source_id", name="uq_research_source_attachment"
        ),
        Index("ix_research_source_attachments_experiment", "research_experiment_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    research_experiment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_experiments.id", ondelete="CASCADE"), nullable=False
    )
    research_source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_sources.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
