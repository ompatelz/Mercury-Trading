from collections.abc import Callable
from typing import TypeVar

from app.model_routing.registry import ModelRegistry
from app.model_routing.schemas import RoutingDecision

T = TypeVar("T")


class EscalationPolicy:
    """Named, reviewable conditions for attempting a stronger configured model."""

    def __init__(self, minimum_confidence: float | None = None) -> None:
        self.minimum_confidence = minimum_confidence

    def should_escalate(
        self,
        *,
        schema_valid: bool,
        tool_succeeded: bool,
        confidence: float | None = None,
    ) -> str | None:
        if not schema_valid:
            return "schema_validation_failed"
        if not tool_succeeded:
            return "tool_call_failed"
        if (
            confidence is not None
            and self.minimum_confidence is not None
            and confidence < self.minimum_confidence
        ):
            return "confidence_below_threshold"
        return None


class FallbackExecutor:
    """Executes an explicit fallback chain; callers persist each attempted decision."""

    def __init__(self, registry: ModelRegistry) -> None:
        self.registry = registry

    def run(self, decision: RoutingDecision, execute: Callable[[str], T]) -> tuple[T, list[str]]:
        attempted = [decision.model.model_id, *decision.model.fallback_model_ids]
        errors: list[str] = []
        for model_id in attempted:
            try:
                return execute(model_id), errors
            except (TimeoutError, ConnectionError, ValueError) as exc:
                errors.append(f"{model_id}: {type(exc).__name__}")
        raise RuntimeError(f"all configured model fallbacks failed: {', '.join(errors)}")
