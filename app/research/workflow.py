import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.research.model_client import ResearchModelClient
from app.research.prompts import (
    CRITIC_PROMPT,
    EVALUATION_PROMPT,
    HYPOTHESIS_PROMPT,
    STRATEGY_PROMPT,
)
from app.research.schemas import (
    BacktestToolResult,
    CriticOutput,
    EvaluationOutput,
    HypothesisOutput,
    ModelInvocationMetadata,
    ResearchExperimentRequest,
    ResearchReport,
    StrategySpecification,
)
from app.research.tools import run_backtest_tool

logger = logging.getLogger(__name__)


@dataclass
class ResearchWorkflowState:
    request: ResearchExperimentRequest
    workflow_run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    hypothesis: HypothesisOutput | None = None
    strategy: StrategySpecification | None = None
    backtest: BacktestToolResult | None = None
    evaluation: EvaluationOutput | None = None
    critique: CriticOutput | None = None
    report: ResearchReport | None = None
    node_durations_ms: dict[str, float] = field(default_factory=dict)
    model_calls: int = 0


def run_research_workflow(
    request: ResearchExperimentRequest,
    session: Session,
    model_client: ResearchModelClient,
) -> ResearchWorkflowState:
    state = ResearchWorkflowState(request=request)
    _run_node(state, "hypothesis", lambda: _hypothesis_node(state, model_client))
    _run_node(state, "strategy_specification", lambda: _strategy_node(state, model_client))
    _run_node(state, "backtest_tool", lambda: _backtest_node(state, session))
    _run_node(state, "evaluation", lambda: _evaluation_node(state, model_client))
    _run_node(state, "critique", lambda: _critic_node(state, model_client))
    _run_node(state, "research_report", lambda: _report_node(state))
    return state


def build_model_metadata(
    state: ResearchWorkflowState, model_client: ResearchModelClient
) -> ModelInvocationMetadata:
    return ModelInvocationMetadata(
        provider=model_client.provider,
        model=model_client.model,
        temperature=model_client.temperature,
        prompt_versions={
            "hypothesis": HYPOTHESIS_PROMPT.version,
            "strategy": STRATEGY_PROMPT.version,
            "evaluation": EVALUATION_PROMPT.version,
            "critic": CRITIC_PROMPT.version,
        },
        model_calls=state.model_calls,
        token_usage={},
        estimated_cost=None,
        latency_ms=sum(state.node_durations_ms.values()),
    )


def _run_node(state: ResearchWorkflowState, node: str, func: Any) -> None:
    started = time.perf_counter()
    logger.info(
        "research workflow node started",
        extra={
            "workflow_run_id": state.workflow_run_id,
            "agent_node": node,
            "status": "started",
        },
    )
    try:
        func()
    finally:
        duration_ms = (time.perf_counter() - started) * 1000.0
        state.node_durations_ms[node] = duration_ms
        logger.info(
            "research workflow node finished",
            extra={
                "workflow_run_id": state.workflow_run_id,
                "agent_node": node,
                "duration_ms": duration_ms,
                "status": "finished",
            },
        )


def _hypothesis_node(state: ResearchWorkflowState, model_client: ResearchModelClient) -> None:
    state.hypothesis = model_client.generate_hypothesis(
        objective=state.request.objective,
        symbol=state.request.symbol,
    )
    state.model_calls += 1


def _strategy_node(state: ResearchWorkflowState, model_client: ResearchModelClient) -> None:
    if state.hypothesis is None:
        raise ValueError("hypothesis node must run before strategy node")
    state.strategy = model_client.specify_strategy(state.hypothesis)
    state.model_calls += 1


def _backtest_node(state: ResearchWorkflowState, session: Session) -> None:
    if state.strategy is None:
        raise ValueError("strategy node must run before backtest node")
    state.backtest = run_backtest_tool(state.request, state.strategy, session)


def _evaluation_node(state: ResearchWorkflowState, model_client: ResearchModelClient) -> None:
    if state.backtest is None:
        raise ValueError("backtest node must run before evaluation node")
    state.evaluation = model_client.evaluate_results(state.backtest.metrics)
    state.model_calls += 1


def _critic_node(state: ResearchWorkflowState, model_client: ResearchModelClient) -> None:
    if state.hypothesis is None or state.strategy is None or state.backtest is None:
        raise ValueError("hypothesis, strategy, and backtest must run before critic node")
    if state.evaluation is None:
        raise ValueError("evaluation node must run before critic node")
    state.critique = model_client.critique_experiment(
        hypothesis=state.hypothesis,
        strategy=state.strategy,
        metrics=state.backtest.metrics,
        evaluation=state.evaluation,
    )
    state.model_calls += 1


def _report_node(state: ResearchWorkflowState) -> None:
    if (
        state.hypothesis is None
        or state.strategy is None
        or state.backtest is None
        or state.evaluation is None
        or state.critique is None
    ):
        raise ValueError("all previous workflow nodes must run before report node")
    state.report = ResearchReport(
        research_objective=state.request.objective,
        hypothesis=state.hypothesis.hypothesis,
        strategy_tested=state.backtest.strategy,
        parameters=state.backtest.parameters,
        dataset=state.backtest.dataset,
        performance_metrics=state.backtest.metrics,
        measured_facts=state.evaluation.measured_facts,
        risk_findings=state.evaluation.risk_findings,
        critic_findings=state.critique,
        conclusion=state.evaluation.interpretation,
        suggested_next_experiment=state.critique.suggested_next_experiment,
    )
