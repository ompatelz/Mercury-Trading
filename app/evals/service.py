"""Controlled workflow evaluation and champion promotion."""

from dataclasses import dataclass
from time import perf_counter
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.service import AgentVersionService
from app.evals.benchmarks import (
    DEFAULT_BENCHMARK_NAME,
    DEFAULT_BENCHMARK_VERSION,
    BenchmarkTask,
    get_benchmark,
)
from app.models.agent import WorkflowChampion, WorkflowVersion
from app.models.eval import EvalRun, EvalTaskResult, WorkflowExperiment

DEFAULT_PROMOTION_RULES: dict[str, Any] = {
    "min_task_success_delta": 0.0,
    "max_latency_increase_pct": 0.25,
    "max_cost_increase_pct": 0.25,
    "critical_cases_must_not_regress": True,
}


@dataclass(frozen=True)
class TaskExecution:
    output: dict[str, Any]
    token_usage: dict[str, int]
    estimated_cost: float


class DeterministicWorkflowExecutor:
    """CI executor; manifest overrides model controlled, reviewable changes."""

    def execute(self, task: BenchmarkTask, workflow: WorkflowVersion) -> TaskExecution:
        defaults: dict[str, dict[str, Any]] = {
            "momentum_strategy": {"strategy": "moving_average_crossover", "structured": True},
            "mean_reversion_strategy": {"strategy": "moving_average_crossover", "structured": True},
            "impossible_strategy_rejection": {"reject": True, "failure_type": "invalid_strategy"},
            "lookahead_bias": {"reject": True, "failure_type": "lookahead_bias"},
            "overfitting_detection": {"failure_type": "overfitting", "mentions_oos": True},
            "failed_experiment_critique": {
                "mentions_drawdown": True,
                "suggests_next_experiment": True,
            },
            "memory_retrieval_relevance": {
                "retrieved_lesson_id": "lesson-spy-failure",
                "irrelevant_retrieval": False,
            },
            "next_experiment_selection": {"next_action": "walk_forward_validation"},
        }
        output = dict(defaults[task.task_id])
        overrides = workflow.manifest.get("eval_behavior", {})
        task_override = overrides.get(task.task_id, {})
        if isinstance(task_override, dict):
            output.update(task_override)
        output.setdefault("structured", True)
        token_count = int(workflow.manifest.get("eval_token_usage", 20))
        cost = float(workflow.manifest.get("eval_estimated_cost", 0.0))
        return TaskExecution(output=output, token_usage={"total": token_count}, estimated_cost=cost)


class EvalService:
    def __init__(
        self, session: Session, executor: DeterministicWorkflowExecutor | None = None
    ) -> None:
        self.session = session
        self.executor = executor or DeterministicWorkflowExecutor()

    def run_benchmark(
        self, benchmark_name: str = DEFAULT_BENCHMARK_NAME, workflow_version_id: UUID | None = None
    ) -> EvalRun:
        workflow = self._workflow(workflow_version_id)
        tasks = get_benchmark(benchmark_name)
        run = EvalRun(
            benchmark_name=benchmark_name,
            benchmark_version=DEFAULT_BENCHMARK_VERSION,
            workflow_version_id=workflow.id,
            status="running",
            aggregate_metrics={},
            execution_metadata={
                "workflow_manifest": workflow.manifest,
                "executor": "deterministic_v1",
            },
        )
        self.session.add(run)
        self.session.flush()
        scores = [self._score_task(task, workflow) for task in tasks]
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
                    output=result.output,
                    token_usage=result.token_usage,
                    estimated_cost=result.estimated_cost,
                    failure_type=result.failure_type,
                )
                for result in scores
            ]
        )
        run.status = "completed"
        run.aggregate_metrics = _aggregate(scores, tasks)
        self.session.flush()
        self.session.refresh(run)
        return run

    def create_workflow_experiment(
        self,
        baseline_id: UUID,
        candidate_id: UUID,
        benchmark_name: str = DEFAULT_BENCHMARK_NAME,
        promotion_rules: dict[str, Any] | None = None,
    ) -> WorkflowExperiment:
        rules = {**DEFAULT_PROMOTION_RULES, **(promotion_rules or {})}
        baseline = self.run_benchmark(benchmark_name, baseline_id)
        candidate = self.run_benchmark(benchmark_name, candidate_id)
        comparison, decision, reason = self._compare(baseline, candidate, rules)
        experiment = WorkflowExperiment(
            baseline_workflow_version_id=baseline.workflow_version_id,
            candidate_workflow_version_id=candidate.workflow_version_id,
            benchmark_name=benchmark_name,
            benchmark_version=DEFAULT_BENCHMARK_VERSION,
            baseline_eval_run_id=baseline.id,
            candidate_eval_run_id=candidate.id,
            promotion_config=rules,
            comparison=comparison,
            decision=decision,
            reason=reason,
        )
        self.session.add(experiment)
        self.session.flush()
        self.session.refresh(experiment)
        return experiment

    def promote_candidate(self, candidate_id: UUID) -> WorkflowChampion:
        experiment = self.session.scalar(
            select(WorkflowExperiment)
            .where(
                WorkflowExperiment.candidate_workflow_version_id == candidate_id,
                WorkflowExperiment.decision == "PROMOTED",
            )
            .order_by(WorkflowExperiment.created_at.desc())
        )
        if experiment is None:
            raise ValueError("candidate has no promotion-eligible workflow experiment")
        candidate = self._workflow(candidate_id)
        champion = self.session.scalar(
            select(WorkflowChampion).where(WorkflowChampion.component == candidate.name)
        )
        if champion is None:
            champion = WorkflowChampion(
                component=candidate.name,
                workflow_version_id=candidate.id,
                promoted_from_experiment_id=experiment.id,
            )
            self.session.add(champion)
        else:
            champion.workflow_version_id = candidate.id
            champion.promoted_from_experiment_id = experiment.id
        candidate.status = "champion"
        self.session.flush()
        self.session.refresh(champion)
        return champion

    def list_eval_runs(self) -> list[EvalRun]:
        return list(self.session.scalars(select(EvalRun).order_by(EvalRun.created_at.desc())))

    def get_eval_run(self, eval_run_id: UUID) -> EvalRun | None:
        return self.session.get(EvalRun, eval_run_id)

    def list_task_results(self, eval_run_id: UUID) -> list[EvalTaskResult]:
        return list(
            self.session.scalars(
                select(EvalTaskResult)
                .where(EvalTaskResult.eval_run_id == eval_run_id)
                .order_by(EvalTaskResult.id)
            )
        )

    def list_experiments(self) -> list[WorkflowExperiment]:
        return list(
            self.session.scalars(
                select(WorkflowExperiment).order_by(WorkflowExperiment.created_at.desc())
            )
        )

    def compare_runs(
        self,
        baseline_eval_run_id: UUID,
        candidate_eval_run_id: UUID,
        min_task_success_delta: float = 0.0,
        max_latency_increase_pct: float = 0.25,
    ) -> Any:
        """Compatibility wrapper for the original comparison endpoint."""
        baseline = self.get_eval_run(baseline_eval_run_id)
        candidate = self.get_eval_run(candidate_eval_run_id)
        if (
            baseline is None
            or candidate is None
            or baseline.status != "completed"
            or candidate.status != "completed"
        ):
            raise ValueError("eval run not found or incomplete")
        if baseline.benchmark_name != candidate.benchmark_name:
            raise ValueError("eval runs must use the same benchmark")
        comparison, decision, reason = self._compare(
            baseline,
            candidate,
            {
                **DEFAULT_PROMOTION_RULES,
                "min_task_success_delta": min_task_success_delta,
                "max_latency_increase_pct": max_latency_increase_pct,
            },
        )
        from app.models.agent import VersionComparison

        record = VersionComparison(
            baseline_workflow_version_id=baseline.workflow_version_id,
            candidate_workflow_version_id=candidate.workflow_version_id,
            benchmark_name=baseline.benchmark_name,
            metric_differences={
                "task_success_rate": comparison["task_success_delta"],
                "average_latency_ms": comparison["latency_delta_ms"],
                "estimated_cost": comparison["cost_delta"],
            },
            decision="promote" if decision == "PROMOTED" else "reject",
            reason=reason,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def _workflow(self, workflow_id: UUID | None) -> WorkflowVersion:
        if workflow_id is None:
            return AgentVersionService(self.session).ensure_default_workflow()
        workflow = self.session.get(WorkflowVersion, workflow_id)
        if workflow is None:
            raise ValueError("workflow version not found")
        return workflow

    def _score_task(self, task: BenchmarkTask, workflow: WorkflowVersion) -> "_TaskScore":
        started = perf_counter()
        execution = self.executor.execute(task, workflow)
        output = execution.output
        scores = {rule: _rule_score(rule, output, task) for rule in task.scoring_rules}
        success = all(value == 1.0 for value in scores.values())
        findings = (
            [] if success else [f"failed: {key}" for key, value in scores.items() if value == 0.0]
        )
        return _TaskScore(
            task.task_id,
            task.task_type,
            success,
            scores,
            findings,
            round((perf_counter() - started) * 1000.0, 6),
            output,
            execution.token_usage,
            execution.estimated_cost,
            str(output.get("failure_type")) if output.get("failure_type") else None,
        )

    def _compare(
        self, baseline: EvalRun, candidate: EvalRun, rules: dict[str, Any]
    ) -> tuple[dict[str, Any], str, str]:
        b, c = baseline.aggregate_metrics, candidate.aggregate_metrics
        critical_regressions = [
            key
            for key in b["critical_task_success"]
            if b["critical_task_success"][key] and not c["critical_task_success"].get(key, False)
        ]
        success_delta = round(float(c["task_success_rate"]) - float(b["task_success_rate"]), 6)
        latency_limit = (
            float(b["average_latency_ms"]) * (1 + float(rules["max_latency_increase_pct"])) + 1.0
        )
        cost_limit = (
            float(b["estimated_cost"]) * (1 + float(rules["max_cost_increase_pct"])) + 0.000001
        )
        passed = (
            success_delta >= float(rules["min_task_success_delta"])
            and float(c["average_latency_ms"]) <= latency_limit
            and float(c["estimated_cost"]) <= cost_limit
            and (not rules["critical_cases_must_not_regress"] or not critical_regressions)
        )
        comparison = {
            "task_success_delta": success_delta,
            "latency_delta_ms": round(
                float(c["average_latency_ms"]) - float(b["average_latency_ms"]), 6
            ),
            "cost_delta": round(float(c["estimated_cost"]) - float(b["estimated_cost"]), 6),
            "critical_regressions": critical_regressions,
            "baseline": b,
            "candidate": c,
        }
        if passed:
            return (
                comparison,
                "PROMOTED",
                "Candidate met success, critical-regression, latency, and cost rules.",
            )
        return (
            comparison,
            "REJECTED",
            "Candidate failed promotion rules: "
            + ", ".join(critical_regressions or ["success, latency, or cost threshold"]),
        )


@dataclass
class _TaskScore:
    task_id: str
    task_type: str
    success: bool
    scores: dict[str, float]
    findings: list[str]
    latency_ms: float
    output: dict[str, Any]
    token_usage: dict[str, int]
    estimated_cost: float
    failure_type: str | None


def _rule_score(rule: str, output: dict[str, Any], task: BenchmarkTask) -> float:
    if rule == "structured_output":
        return 1.0 if output.get("structured") is True else 0.0
    if rule == "strategy_schema_valid":
        return 1.0 if output.get("strategy") in task.fixtures["approved_strategies"] else 0.0
    if rule == "invalid_strategy_rejected":
        return (
            1.0
            if output.get("reject") and output.get("failure_type") == "invalid_strategy"
            else 0.0
        )
    if rule == "lookahead_detected":
        return (
            1.0 if output.get("reject") and output.get("failure_type") == "lookahead_bias" else 0.0
        )
    if rule == "overfitting_detected":
        return (
            1.0
            if output.get("failure_type") == "overfitting" and output.get("mentions_oos")
            else 0.0
        )
    if rule == "critique_grounded":
        return (
            1.0
            if output.get("mentions_drawdown") and output.get("suggests_next_experiment")
            else 0.0
        )
    if rule == "memory_retrieval_relevance":
        return (
            1.0
            if output.get("retrieved_lesson_id") == task.expected_constraints["retrieved_lesson_id"]
            and not output.get("irrelevant_retrieval")
            else 0.0
        )
    if rule == "tool_use_correct":
        return 1.0 if output.get("retrieved_lesson_id") else 0.0
    if rule == "workflow_action_valid":
        return 1.0 if output.get("next_action") in task.fixtures["allowed_actions"] else 0.0
    if rule == "task_success":
        return 1.0
    raise ValueError(f"unknown scoring rule: {rule}")


def _aggregate(results: list[_TaskScore], tasks: tuple[BenchmarkTask, ...]) -> dict[str, Any]:
    critical = {
        task.task_id: result.success
        for task, result in zip(tasks, results, strict=True)
        if task.critical
    }
    invalid = [item for item in results if item.task_type == "invalid_strategy_rejection"]
    return {
        "task_count": len(results),
        "task_success_rate": round(sum(item.success for item in results) / len(results), 6),
        "critical_failure_rate": round(
            sum(not value for value in critical.values()) / len(critical), 6
        ),
        "critical_task_success": critical,
        "average_latency_ms": round(sum(item.latency_ms for item in results) / len(results), 6),
        "estimated_cost": round(sum(item.estimated_cost for item in results), 6),
        "invalid_strategy_rejection_rate": round(
            sum(item.success for item in invalid) / len(invalid), 6
        )
        if invalid
        else 1.0,
        "token_usage": sum(item.token_usage.get("total", 0) for item in results),
    }
