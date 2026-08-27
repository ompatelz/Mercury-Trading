from sqlalchemy.orm import Session

from app.agents.service import AgentVersionService
from app.evals.service import EvalService
from app.governance.service import DecisionService
from app.models.agent import WorkflowVersion


def test_decision_service_records_rules_and_replays_integrity(db_session: Session) -> None:
    service = DecisionService(db_session)
    decision = service.record(
        decision_type="HUMAN_OVERRIDE",
        outcome="APPROVED",
        actor="test",
        reason="operator approved a dry-run decision",
        inputs={"request_id": "req-1"},
        rules=[
            {
                "rule": "PAPER_ONLY",
                "threshold": "execution_mode must be PAPER",
                "observed_value": "PAPER",
                "passed": True,
            }
        ],
    )
    db_session.commit()

    explanation = service.explain(decision.id)

    assert explanation is not None
    assert explanation["integrity"]["verified"] is True
    assert explanation["content_hash"] == decision.content_hash
    assert explanation["rules"][0]["rule_version"] == "v1"


def test_workflow_experiment_writes_decision_provenance(db_session: Session) -> None:
    versions = AgentVersionService(db_session)
    baseline = versions.ensure_default_workflow()
    candidate = WorkflowVersion(
        name="research_workflow",
        version="critical-regression-v3",
        backtester_version="moving_average_backtester:v1",
        retrieval_config={},
        tool_versions={},
        manifest={"eval_behavior": {"lookahead_bias": {"reject": False}}},
        status="candidate",
    )
    db_session.add(candidate)
    db_session.flush()

    experiment = EvalService(db_session).create_workflow_experiment(baseline.id, candidate.id)
    decisions = DecisionService(db_session).list_decisions(decision_type="WORKFLOW_REJECTION")

    assert experiment.decision == "REJECTED"
    assert len(decisions) == 1
    assert decisions[0].workflow_experiment_id == experiment.id
    assert DecisionService(db_session).explain(decisions[0].id)["integrity"]["verified"] is True
