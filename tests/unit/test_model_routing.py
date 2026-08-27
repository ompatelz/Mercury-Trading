import pytest

from app.model_routing.execution import FallbackExecutor
from app.model_routing.registry import ModelRegistry
from app.model_routing.schemas import (
    ModelBenchmark,
    ModelCapability,
    ResearchTaskType,
    RoutingPolicy,
    RoutingRequest,
)
from app.model_routing.service import ModelRouter
from app.model_routing.tracking import ModelUsageService


def _model(model_id: str, *, enabled: bool = True, cost: float = 0.0) -> ModelCapability:
    return ModelCapability(
        model_id=model_id,
        provider="test",
        version="v1",
        context_window=8192,
        supports_structured_output=True,
        supports_tools=False,
        enabled=enabled,
        input_cost_per_1k=cost,
        output_cost_per_1k=cost,
        fallback_model_ids=("backup",) if model_id == "primary" else (),
    )


def _benchmark(model_id: str, quality: float, latency: float) -> ModelBenchmark:
    return ModelBenchmark(
        model_id=model_id,
        task_type=ResearchTaskType.CRITIQUE,
        quality_score=quality,
        success_rate=quality,
        structured_output_reliability=quality,
        average_latency_ms=latency,
        sample_count=10,
    )


def test_policy_uses_measured_quality_cost_and_latency_components() -> None:
    registry = ModelRegistry([_model("strong", cost=0.1), _model("cheap", cost=0.005)])
    router = ModelRouter(registry, [_benchmark("strong", 0.95, 900), _benchmark("cheap", 0.8, 100)])
    fast = router.select(
        RoutingRequest(task_type=ResearchTaskType.CRITIQUE, policy=RoutingPolicy.FAST)
    )
    high = router.select(
        RoutingRequest(task_type=ResearchTaskType.CRITIQUE, policy=RoutingPolicy.HIGH_QUALITY)
    )
    assert fast.model.model_id == "cheap"
    assert high.model.model_id == "strong"
    assert {"quality_component", "cost_penalty", "latency_penalty", "utility"} <= set(
        high.score_components
    )


def test_disabled_models_and_budget_are_excluded() -> None:
    registry = ModelRegistry([_model("disabled", enabled=False), _model("cheap", cost=0.05)])
    router = ModelRouter(registry, [_benchmark("cheap", 0.8, 100)])
    decision = router.select(
        RoutingRequest(task_type=ResearchTaskType.CRITIQUE, remaining_cost=0.2)
    )
    assert decision.model.model_id == "cheap"
    with pytest.raises(ValueError, match="quality-protected"):
        router.select(
            RoutingRequest(task_type=ResearchTaskType.CRITIQUE, critical=True, remaining_cost=0.01)
        )


def test_fallback_is_explicit_and_stops_at_backup() -> None:
    registry = ModelRegistry([_model("primary"), _model("backup")])
    decision = ModelRouter(registry, [_benchmark("primary", 0.9, 100)]).select(
        RoutingRequest(task_type=ResearchTaskType.CRITIQUE)
    )
    output, errors = FallbackExecutor(registry).run(
        decision,
        lambda model_id: (
            (_ for _ in ()).throw(ConnectionError()) if model_id == "primary" else "ok"
        ),
    )
    assert output == "ok"
    assert errors == ["primary: ConnectionError"]


def test_usage_tracking_persists_explainable_cost(db_session) -> None:
    registry = ModelRegistry([_model("cheap", cost=0.1)])
    decision = ModelRouter(registry, [_benchmark("cheap", 0.8, 50)]).select(
        RoutingRequest(task_type=ResearchTaskType.CRITIQUE)
    )
    ModelUsageService(db_session).record(
        decision,
        agent="critic_agent",
        success=True,
        input_tokens=1000,
        output_tokens=500,
        latency_ms=50,
    )
    summary = ModelUsageService(db_session).summary()
    assert summary[0]["model"] == "cheap"
    assert summary[0]["total_cost"] == pytest.approx(0.15)
