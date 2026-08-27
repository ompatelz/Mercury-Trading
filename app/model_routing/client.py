import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from app.model_routing.schemas import (
    ResearchTaskType,
    RoutingDecision,
    RoutingPolicy,
    RoutingRequest,
)
from app.model_routing.service import ModelRouter
from app.research.model_client import ResearchModelClient
from app.research.schemas import (
    CriticOutput,
    EvaluationOutput,
    HypothesisOutput,
    StrategySpecification,
)

T = TypeVar("T")


@dataclass(frozen=True)
class RoutedInvocation:
    decision: RoutingDecision
    agent: str
    latency_ms: float
    success: bool


class RoutingResearchModelClient:
    """Routes workflow nodes while retaining Mercury's typed structured contracts."""

    provider = "local"
    model = "adaptive_router"
    temperature: float | None = 0.0

    def __init__(
        self, delegate: ResearchModelClient, router: ModelRouter, policy: RoutingPolicy
    ) -> None:
        self.delegate = delegate
        self.router = router
        self.policy = policy
        self.invocations: list[RoutedInvocation] = []

    def generate_hypothesis(self, objective: str, symbol: str) -> HypothesisOutput:
        return self._invoke(
            ResearchTaskType.HYPOTHESIS_GENERATION,
            "hypothesis_agent",
            lambda: self.delegate.generate_hypothesis(objective, symbol),
        )

    def specify_strategy(self, hypothesis: HypothesisOutput) -> StrategySpecification:
        return self._invoke(
            ResearchTaskType.STRATEGY_GENERATION,
            "strategy_generation_agent",
            lambda: self.delegate.specify_strategy(hypothesis),
        )

    def evaluate_results(self, metrics: dict[str, object]) -> EvaluationOutput:
        return self._invoke(
            ResearchTaskType.RISK_EXPLANATION,
            "evaluation_agent",
            lambda: self.delegate.evaluate_results(metrics),
        )

    def critique_experiment(
        self,
        hypothesis: HypothesisOutput,
        strategy: StrategySpecification,
        metrics: dict[str, object],
        evaluation: EvaluationOutput,
    ) -> CriticOutput:
        return self._invoke(
            ResearchTaskType.CRITIQUE,
            "critic_agent",
            lambda: self.delegate.critique_experiment(hypothesis, strategy, metrics, evaluation),
        )

    def _invoke(self, task_type: ResearchTaskType, agent: str, call: Callable[[], T]) -> T:
        decision = self.router.select(RoutingRequest(task_type=task_type, policy=self.policy))
        started = time.perf_counter()
        try:
            output = call()
        except Exception:
            self.invocations.append(
                RoutedInvocation(decision, agent, (time.perf_counter() - started) * 1000, False)
            )
            raise
        self.invocations.append(
            RoutedInvocation(decision, agent, (time.perf_counter() - started) * 1000, True)
        )
        return output
