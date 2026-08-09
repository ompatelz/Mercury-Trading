import time
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.service import AgentVersionService
from app.evals.benchmarks import DEFAULT_BENCHMARK_NAME, DEFAULT_BENCHMARK_TASKS, BenchmarkTask
from app.models.agent import VersionComparison, WorkflowVersion
from app.models.eval import EvalRun, EvalTaskResult


class EvalService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def run_benchmark(
        self,
        benchmark_name: str = DEFAULT_BENCHMARK_NAME,
        workflow_version_id: UUID | None = None,
    ) -> EvalRun:
        if workflow_version_id is None:
            workflow_version = AgentVersionService(self.session).ensure_default_workflow()
        else:
            selected_workflow_version = self.session.get(WorkflowVersion, workflow_version_id)
            if selected_workflow_version is None:
                raise ValueError("workflow version not found")
            workflow_version = selected_workflow_version

        run = EvalRun(
            benchmark_name=benchmark_name,
            workflow_version_id=workflow_version.id,
            status="running",
            aggregate_metrics={},
        )
        self.session.add(run)
        self.session.flush()

        results = [_score_task(task) for task in DEFAULT_BENCHMARK_TASKS]
        self.session.add_all(
            [
                EvalTaskResult(
                    eval_run_id=run.id,
                    task_id=result.task_id,
                    task_type=result.task_type,
                    success=result.success,
                    scores=result.scores,
                    findings=result.findings,
                    latency_ms=result.latency_ms,
                )
                for result in results
            ]
        )
        run.status = "completed"
        run.aggregate_metrics = _aggregate(results)
        self.session.flush()
        self.session.refresh(run)
        return run

    def get_eval_run(self, eval_run_id: UUID) -> EvalRun | None:
        return self.session.get(EvalRun, eval_run_id)

    def list_eval_runs(self) -> list[EvalRun]:
        return list(self.session.scalars(select(EvalRun).order_by(EvalRun.created_at.desc())))

    def list_task_results(self, eval_run_id: UUID) -> list[EvalTaskResult]:
        return list(
            self.session.scalars(
                select(EvalTaskResult)
                .where(EvalTaskResult.eval_run_id == eval_run_id)
                .order_by(EvalTaskResult.id)
            )
        )

    def compare_runs(
        self,
        baseline_eval_run_id: UUID,
        candidate_eval_run_id: UUID,
        min_task_success_delta: float = 0.0,
        max_latency_increase_pct: float = 0.25,
    ) -> VersionComparison:
        baseline = self._completed_run(baseline_eval_run_id)
        candidate = self._completed_run(candidate_eval_run_id)
        if baseline.benchmark_name != candidate.benchmark_name:
            raise ValueError("eval runs must use the same benchmark")

        baseline_metrics = baseline.aggregate_metrics
        candidate_metrics = candidate.aggregate_metrics
        deltas = {
            "task_success_rate": round(
                candidate_metrics["task_success_rate"] - baseline_metrics["task_success_rate"],
                6,
            ),
            "invalid_strategy_rejection_rate": round(
                candidate_metrics["invalid_strategy_rejection_rate"]
                - baseline_metrics["invalid_strategy_rejection_rate"],
                6,
            ),
            "average_latency_ms": round(
                candidate_metrics["average_latency_ms"] - baseline_metrics["average_latency_ms"],
                6,
            ),
        }
        latency_ceiling = max(
            baseline_metrics["average_latency_ms"] * (1 + max_latency_increase_pct),
            baseline_metrics["average_latency_ms"] + 1.0,
        )
        promoted = (
            deltas["task_success_rate"] >= min_task_success_delta
            and candidate_metrics["invalid_strategy_rejection_rate"]
            >= baseline_metrics["invalid_strategy_rejection_rate"]
            and candidate_metrics["average_latency_ms"] <= latency_ceiling
        )
        comparison = VersionComparison(
            baseline_workflow_version_id=baseline.workflow_version_id,
            candidate_workflow_version_id=candidate.workflow_version_id,
            benchmark_name=baseline.benchmark_name,
            metric_differences=deltas,
            decision="promote" if promoted else "reject",
            reason=(
                "Candidate met success, invalid-strategy detection, and latency thresholds."
                if promoted
                else "Candidate failed at least one promotion threshold."
            ),
        )
        self.session.add(comparison)
        self.session.flush()
        self.session.refresh(comparison)
        return comparison

    def _completed_run(self, eval_run_id: UUID) -> EvalRun:
        run = self.session.get(EvalRun, eval_run_id)
        if run is None:
            raise ValueError("eval run not found")
        if run.status != "completed":
            raise ValueError("eval run is not complete")
        return run


class _TaskScore:
    def __init__(
        self,
        task_id: str,
        task_type: str,
        success: bool,
        scores: dict[str, float],
        findings: list[str],
        latency_ms: float,
    ) -> None:
        self.task_id = task_id
        self.task_type = task_type
        self.success = success
        self.scores = scores
        self.findings = findings
        self.latency_ms = latency_ms


def _score_task(task: BenchmarkTask) -> _TaskScore:
    started = time.perf_counter()
    output = _deterministic_agent_response(task)
    found_terms = sum(1 for term in task.expected_terms if term.lower() in output.lower())
    structured_output = output.startswith("{") and output.endswith("}")
    detects_required_failure = task.required_failure is None or task.required_failure in output
    success = (
        found_terms == len(task.expected_terms) and structured_output and detects_required_failure
    )
    return _TaskScore(
        task_id=task.task_id,
        task_type=task.task_type,
        success=success,
        scores={
            "expected_term_rate": found_terms / len(task.expected_terms),
            "structured_output": 1.0 if structured_output else 0.0,
            "required_failure_detected": 1.0 if detects_required_failure else 0.0,
        },
        findings=[] if success else ["deterministic response missed benchmark expectations"],
        latency_ms=round((time.perf_counter() - started) * 1000.0, 6),
    )


def _deterministic_agent_response(task: BenchmarkTask) -> str:
    if task.required_failure == "lookahead_bias":
        return (
            '{"finding":"look-ahead bias uses future tomorrow close and must be rejected",'
            '"failure":"lookahead_bias"}'
        )
    if task.required_failure == "overfitting":
        return (
            '{"finding":"overfit strategy requires out-of-sample validation",'
            '"failure":"overfitting"}'
        )
    if "BTC" in task.prompt:
        return '{"strategy":"BTC mean-reversion strategy with bounded risk"}'
    return '{"strategy":"SPY moving average momentum strategy"}'


def _aggregate(results: list[_TaskScore]) -> dict[str, float]:
    success_count = sum(1 for result in results if result.success)
    invalid_tasks = [
        result for result in results if result.task_type == "invalid_strategy_detection"
    ]
    invalid_success = sum(1 for result in invalid_tasks if result.success)
    return {
        "task_count": float(len(results)),
        "task_success_rate": round(success_count / len(results), 6),
        "invalid_strategy_rejection_rate": round(invalid_success / len(invalid_tasks), 6)
        if invalid_tasks
        else 1.0,
        "average_latency_ms": round(
            sum(result.latency_ms for result in results) / len(results),
            6,
        ),
        "estimated_cost": 0.0,
    }
