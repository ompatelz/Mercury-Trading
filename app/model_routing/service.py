from collections.abc import Iterable

from app.model_routing.registry import ModelRegistry
from app.model_routing.schemas import (
    ModelBenchmark,
    RoutingDecision,
    RoutingPolicy,
    RoutingRequest,
)


class ModelRouter:
    """Select a model from measured, task-specific evidence with visible components."""

    def __init__(self, registry: ModelRegistry, benchmarks: Iterable[ModelBenchmark] = ()) -> None:
        self.registry = registry
        self._benchmarks = {(item.model_id, item.task_type): item for item in benchmarks}

    def select(self, request: RoutingRequest) -> RoutingDecision:
        candidates = [
            model
            for model in self.registry.enabled()
            if request.task_type in model.task_types
            and (not request.requires_structured_output or model.supports_structured_output)
            and (not request.requires_tools or model.supports_tools)
        ]
        if not candidates:
            raise ValueError(f"no enabled model supports {request.task_type}")
        scored = [(self._score(model.model_id, request), model) for model in candidates]
        feasible = [
            (score, model) for score, model in scored if self._budget_allows(model, request)
        ]
        if feasible:
            components, model = max(feasible, key=lambda item: item[0]["utility"])
            downgraded = bool(request.remaining_cost is not None and len(feasible) < len(scored))
        elif request.critical:
            raise ValueError("budget cannot satisfy the quality-protected critical task")
        else:
            components, model = max(scored, key=lambda item: item[0]["utility"])
            downgraded = True
        return RoutingDecision(
            model=model,
            task_type=request.task_type,
            policy=request.policy,
            score_components=components,
            downgraded_for_budget=downgraded,
            reason=(
                f"selected from {len(candidates)} compatible models using measured task evidence; "
                f"utility={components['utility']:.6f}"
            ),
        )

    def _score(self, model_id: str, request: RoutingRequest) -> dict[str, float]:
        benchmark = self._benchmarks.get((model_id, request.task_type))
        if benchmark is None or benchmark.sample_count == 0:
            quality = success = structured = 0.0
            latency = 1_000_000.0
        else:
            quality = benchmark.quality_score
            success = benchmark.success_rate
            structured = benchmark.structured_output_reliability
            latency = benchmark.average_latency_ms
        model = self.registry.get(model_id)
        estimated_cost = model.input_cost_per_1k + model.output_cost_per_1k
        weights = {
            RoutingPolicy.FAST: (0.20, 0.45, 0.35),
            RoutingPolicy.BALANCED: (0.55, 0.25, 0.20),
            RoutingPolicy.HIGH_QUALITY: (0.80, 0.10, 0.10),
        }[request.policy]
        quality_component = (quality + success + structured) / 3
        cost_penalty = estimated_cost
        latency_penalty = latency / 1000.0
        utility = (
            weights[0] * quality_component
            - weights[1] * cost_penalty
            - weights[2] * latency_penalty
        )
        return {
            "quality_score": quality,
            "success_rate": success,
            "structured_output_reliability": structured,
            "estimated_call_cost": estimated_cost,
            "latency_ms": latency,
            "quality_component": quality_component,
            "cost_penalty": cost_penalty,
            "latency_penalty": latency_penalty,
            "utility": utility,
        }

    @staticmethod
    def _budget_allows(model: object, request: RoutingRequest) -> bool:
        estimated_cost = model.input_cost_per_1k + model.output_cost_per_1k  # type: ignore[attr-defined]
        if request.max_cost is not None and estimated_cost > request.max_cost:
            return False
        if request.remaining_cost is not None and estimated_cost > request.remaining_cost:
            return False
        return request.remaining_calls is None or request.remaining_calls > 0
