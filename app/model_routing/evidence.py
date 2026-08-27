from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.model_routing.schemas import ModelBenchmark, ResearchTaskType
from app.models.agent import WorkflowVersion
from app.models.eval import EvalRun, EvalTaskResult


class EvalEvidenceService:
    """Turns existing persisted workflow-eval results into model/task evidence."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def benchmarks(self) -> list[ModelBenchmark]:
        rows = self.session.execute(
            select(EvalTaskResult, EvalRun, WorkflowVersion)
            .join(EvalRun, EvalTaskResult.eval_run_id == EvalRun.id)
            .join(WorkflowVersion, EvalRun.workflow_version_id == WorkflowVersion.id)
            .where(EvalRun.status == "completed")
        ).all()
        grouped: dict[tuple[str, ResearchTaskType], list[EvalTaskResult]] = defaultdict(list)
        for result, _, workflow in rows:
            try:
                task_type = ResearchTaskType(result.task_type)
            except ValueError:
                continue
            model = workflow.manifest.get("model", {}).get("name")
            if isinstance(model, str):
                grouped[(model, task_type)].append(result)
        evidence: list[ModelBenchmark] = []
        for (model_id, task_type), results in grouped.items():
            quality = [float(item.scores.get("quality", item.success)) for item in results]
            structured = [float(item.output.get("structured", item.success)) for item in results]
            evidence.append(
                ModelBenchmark(
                    model_id=model_id,
                    task_type=task_type,
                    quality_score=sum(quality) / len(quality),
                    success_rate=sum(item.success for item in results) / len(results),
                    structured_output_reliability=sum(structured) / len(structured),
                    average_latency_ms=sum(item.latency_ms for item in results) / len(results),
                    sample_count=len(results),
                )
            )
        return evidence
