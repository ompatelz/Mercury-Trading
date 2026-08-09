from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.market_data.normalization import normalize_bars
from app.market_data.repository import MarketDataRepository
from app.research.model_client import RuleBasedResearchModelClient
from app.research.schemas import (
    CriticOutput,
    EvaluationOutput,
    HypothesisOutput,
    ResearchExperimentRequest,
    StrategySpecification,
)
from app.research.service import ResearchExperimentService
from app.research.tools import run_backtest_tool
from app.research.workflow import run_research_workflow
from tests.conftest import sample_raw_bars


def research_request() -> ResearchExperimentRequest:
    return ResearchExperimentRequest(
        objective="Explore trend-following behavior on MSFT with deterministic data",
        symbol="MSFT",
        start_date="2024-01-01",
        end_date="2024-01-11",
    )


def seed_bars(session: Session) -> None:
    bars = normalize_bars(sample_raw_bars(), symbol="MSFT", interval="1d")
    MarketDataRepository(session).upsert_bars(bars)
    session.commit()


def test_backtest_tool_rejects_unknown_strategy(db_session: Session) -> None:
    seed_bars(db_session)
    spec = StrategySpecification(strategy="unknown", symbol="MSFT", parameters={})

    with pytest.raises(ValueError, match="unknown strategy"):
        run_backtest_tool(research_request(), spec, db_session)


def test_research_workflow_completes_with_mocked_model(db_session: Session) -> None:
    seed_bars(db_session)
    state = run_research_workflow(
        request=research_request(),
        session=db_session,
        model_client=RuleBasedResearchModelClient(),
    )

    assert state.hypothesis is not None
    assert state.strategy is not None
    assert state.backtest is not None
    assert state.evaluation is not None
    assert state.critique is not None
    assert state.report is not None
    assert state.model_calls == 4
    assert state.backtest.metrics["number_of_trades"] >= 1


def test_research_service_persists_completed_experiment(db_session: Session) -> None:
    seed_bars(db_session)
    service = ResearchExperimentService(db_session, RuleBasedResearchModelClient())
    record = service.run_research_experiment(research_request())
    db_session.commit()

    assert record.status == "completed"
    assert record.backtest_experiment_id is not None
    assert record.model_metadata["provider"] == "local"
    assert record.workflow_metadata["tool_calls"] == 1
    assert record.report["performance_metrics"]["ending_equity"] == record.metrics["ending_equity"]


class InvalidStrategyModel:
    provider = "test"
    model = "invalid_strategy"
    temperature = 0.0

    def generate_hypothesis(self, objective: str, symbol: str) -> HypothesisOutput:
        _ = objective
        return HypothesisOutput(
            hypothesis="Invalid strategy should fail before deterministic execution.",
            rationale="This tests workflow failure boundaries.",
            symbol=symbol,
            strategy_family="not_registered",
            parameters_to_test={"fast_window": 2, "slow_window": 3},
            expected_behavior="The registry rejects this strategy.",
            failure_conditions=["Registry validation does not reject it"],
        )

    def specify_strategy(self, hypothesis: HypothesisOutput) -> StrategySpecification:
        return StrategySpecification(
            strategy=hypothesis.strategy_family,
            symbol=hypothesis.symbol,
            parameters=hypothesis.parameters_to_test,
        )

    def evaluate_results(self, metrics: dict[str, object]) -> EvaluationOutput:
        _ = metrics
        raise AssertionError("evaluation should not run after invalid strategy")

    def critique_experiment(
        self,
        hypothesis: HypothesisOutput,
        strategy: StrategySpecification,
        metrics: dict[str, object],
        evaluation: EvaluationOutput,
    ) -> CriticOutput:
        _: tuple[Any, ...] = (hypothesis, strategy, metrics, evaluation)
        raise AssertionError("critique should not run after invalid strategy")


def test_research_workflow_stops_on_invalid_strategy(db_session: Session) -> None:
    seed_bars(db_session)

    with pytest.raises(ValueError, match="unknown strategy"):
        run_research_workflow(
            request=research_request(),
            session=db_session,
            model_client=InvalidStrategyModel(),
        )
