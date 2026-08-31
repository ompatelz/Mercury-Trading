from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.agent import ResearchTraceEvent
from app.models.experiment import ResearchExperiment
from app.models.research_source import ResearchSource, ResearchSourceAttachment
from app.research.schemas import ResearchSourceCreateRequest

MAX_ATTACHMENTS_PER_EXPERIMENT = 10
MAX_SOURCE_BYTES = 128 * 1024
MAX_TOTAL_SOURCE_BYTES_PER_EXPERIMENT = 512 * 1024


@dataclass(frozen=True)
class AttachedResearchSource:
    attachment: ResearchSourceAttachment
    source: ResearchSource
    deduplicated: bool


class ResearchSourceService:
    """Stores source documents as evidence only, never as strategy/backtest inputs."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def attach(
        self, research_experiment_id: UUID, request: ResearchSourceCreateRequest
    ) -> AttachedResearchSource:
        experiment = self._require_experiment(research_experiment_id)
        content_bytes = request.content.encode("utf-8")
        if len(content_bytes) > MAX_SOURCE_BYTES:
            raise ValueError(f"source exceeds the {MAX_SOURCE_BYTES} byte limit")

        checksum = sha256(content_bytes).hexdigest()
        source = self.session.scalar(
            select(ResearchSource).where(ResearchSource.sha256 == checksum)
        )
        deduplicated = source is not None
        current_count, current_bytes = self._experiment_quota(research_experiment_id)
        if current_count >= MAX_ATTACHMENTS_PER_EXPERIMENT:
            raise ValueError(
                "research experiment already has "
                f"{MAX_ATTACHMENTS_PER_EXPERIMENT} source attachments"
            )
        if current_bytes + len(content_bytes) > MAX_TOTAL_SOURCE_BYTES_PER_EXPERIMENT:
            raise ValueError(
                f"source attachments exceed the {MAX_TOTAL_SOURCE_BYTES_PER_EXPERIMENT} byte limit"
            )

        if source is None:
            source = ResearchSource(
                sha256=checksum,
                content_type=request.content_type,
                content=request.content,
                byte_size=len(content_bytes),
            )
            self.session.add(source)
            self.session.flush()
        elif source.content_type != request.content_type:
            raise ValueError("a duplicate source must retain its original content type")

        existing = self.session.scalar(
            select(ResearchSourceAttachment).where(
                ResearchSourceAttachment.research_experiment_id == research_experiment_id,
                ResearchSourceAttachment.research_source_id == source.id,
            )
        )
        if existing is not None:
            raise ValueError("this source is already attached to the research experiment")

        attachment = ResearchSourceAttachment(
            research_experiment_id=research_experiment_id,
            research_source_id=source.id,
            title=request.title,
            original_filename=request.original_filename,
        )
        self.session.add(attachment)
        self.session.add(
            ResearchTraceEvent(
                research_experiment_id=research_experiment_id,
                workflow_run_id=str(
                    experiment.workflow_metadata.get("workflow_run_id", f"source:{experiment.id}")
                ),
                event_type="research_source_attached",
                event_payload={
                    "attachment_id": str(attachment.id),
                    "source_id": str(source.id),
                    "sha256": source.sha256,
                    "content_type": source.content_type,
                    "byte_size": source.byte_size,
                    "deduplicated": deduplicated,
                    "execution_input": False,
                },
            )
        )
        self.session.flush()
        return AttachedResearchSource(
            attachment=attachment, source=source, deduplicated=deduplicated
        )

    def list_for_experiment(self, research_experiment_id: UUID) -> list[AttachedResearchSource]:
        self._require_experiment(research_experiment_id)
        rows = self.session.execute(
            select(ResearchSourceAttachment, ResearchSource)
            .join(ResearchSource, ResearchSource.id == ResearchSourceAttachment.research_source_id)
            .where(ResearchSourceAttachment.research_experiment_id == research_experiment_id)
            .order_by(ResearchSourceAttachment.created_at, ResearchSourceAttachment.id)
        )
        return [
            AttachedResearchSource(attachment=attachment, source=source, deduplicated=False)
            for attachment, source in rows
        ]

    def _require_experiment(self, research_experiment_id: UUID) -> ResearchExperiment:
        experiment = self.session.get(ResearchExperiment, research_experiment_id)
        if experiment is None:
            raise ValueError("research experiment not found")
        return experiment

    def _experiment_quota(self, research_experiment_id: UUID) -> tuple[int, int]:
        count, size = self.session.execute(
            select(
                func.count(ResearchSourceAttachment.id),
                func.coalesce(func.sum(ResearchSource.byte_size), 0),
            )
            .join(ResearchSource, ResearchSource.id == ResearchSourceAttachment.research_source_id)
            .where(ResearchSourceAttachment.research_experiment_id == research_experiment_id)
        ).one()
        return int(count), int(size)
