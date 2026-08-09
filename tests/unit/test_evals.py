from sqlalchemy.orm import Session

from app.agents.service import AgentVersionService
from app.evals.service import EvalService
from app.models.agent import WorkflowVersion


def test_eval_runner_stores_deterministic_scores(db_session: Session) -> None:
    run = EvalService(db_session).run_benchmark()
    db_session.commit()

    results = EvalService(db_session).list_task_results(run.id)

    assert run.status == "completed"
    assert run.aggregate_metrics["task_success_rate"] == 1.0
    assert run.aggregate_metrics["invalid_strategy_rejection_rate"] == 1.0
    assert run.aggregate_metrics["estimated_cost"] == 0.0
    assert len(results) == 4
    assert all(result.success for result in results)


def test_promotion_rules_promote_candidate_that_matches_baseline(db_session: Session) -> None:
    version_service = AgentVersionService(db_session)
    baseline_workflow = version_service.ensure_default_workflow()
    candidate_workflow = WorkflowVersion(
        name="research_workflow",
        version="v2",
        backtester_version="moving_average_backtester:v1",
        retrieval_config={"top_k": 2, "min_similarity": 0.1},
        tool_versions={"backtest_tool": "v1", "lesson_extractor": "v1"},
        status="candidate",
    )
    db_session.add(candidate_workflow)
    db_session.flush()

    eval_service = EvalService(db_session)
    baseline = eval_service.run_benchmark(workflow_version_id=baseline_workflow.id)
    candidate = eval_service.run_benchmark(workflow_version_id=candidate_workflow.id)
    comparison = eval_service.compare_runs(baseline.id, candidate.id)
    db_session.commit()

    assert comparison.decision == "promote"
    assert comparison.baseline_workflow_version_id == baseline_workflow.id
    assert comparison.candidate_workflow_version_id == candidate_workflow.id
    assert comparison.metric_differences["task_success_rate"] == 0.0


def test_promotion_rules_reject_regressed_candidate(db_session: Session) -> None:
    version_service = AgentVersionService(db_session)
    baseline_workflow = version_service.ensure_default_workflow()
    candidate_workflow = WorkflowVersion(
        name="research_workflow",
        version="slow-v2",
        backtester_version="moving_average_backtester:v1",
        retrieval_config={"top_k": 3, "min_similarity": 0.05},
        tool_versions={"backtest_tool": "v1", "lesson_extractor": "v1"},
        status="candidate",
    )
    db_session.add(candidate_workflow)
    db_session.flush()

    eval_service = EvalService(db_session)
    baseline = eval_service.run_benchmark(workflow_version_id=baseline_workflow.id)
    candidate = eval_service.run_benchmark(workflow_version_id=candidate_workflow.id)
    candidate.aggregate_metrics = {
        **candidate.aggregate_metrics,
        "task_success_rate": 0.5,
    }
    comparison = eval_service.compare_runs(baseline.id, candidate.id)
    db_session.commit()

    assert comparison.decision == "reject"
    assert comparison.metric_differences["task_success_rate"] == -0.5
