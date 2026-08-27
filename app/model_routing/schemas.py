from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ResearchTaskType(StrEnum):
    HYPOTHESIS_GENERATION = "hypothesis_generation"
    STRATEGY_GENERATION = "strategy_generation"
    CRITIQUE = "critique"
    MEMORY_SUMMARIZATION = "memory_summarization"
    RISK_EXPLANATION = "risk_explanation"
    RESEARCH_PLANNING = "research_planning"
    STRUCTURED_EXTRACTION = "structured_extraction"
    REPORT_WRITING = "report_writing"


class RoutingPolicy(StrEnum):
    FAST = "fast"
    BALANCED = "balanced"
    HIGH_QUALITY = "high_quality"


@dataclass(frozen=True)
class ModelCapability:
    model_id: str
    provider: str
    version: str
    context_window: int
    supports_structured_output: bool
    supports_tools: bool
    enabled: bool = True
    input_cost_per_1k: float = 0.0
    output_cost_per_1k: float = 0.0
    task_types: frozenset[ResearchTaskType] = field(
        default_factory=lambda: frozenset(ResearchTaskType)
    )
    fallback_model_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ModelBenchmark:
    model_id: str
    task_type: ResearchTaskType
    quality_score: float
    success_rate: float
    structured_output_reliability: float
    average_latency_ms: float
    sample_count: int


@dataclass(frozen=True)
class RoutingRequest:
    task_type: ResearchTaskType
    policy: RoutingPolicy = RoutingPolicy.BALANCED
    requires_structured_output: bool = True
    requires_tools: bool = False
    critical: bool = False
    max_cost: float | None = None
    remaining_cost: float | None = None
    remaining_tokens: int | None = None
    remaining_calls: int | None = None


@dataclass(frozen=True)
class RoutingDecision:
    model: ModelCapability
    task_type: ResearchTaskType
    policy: RoutingPolicy
    score_components: dict[str, float]
    reason: str
    downgraded_for_budget: bool = False


@dataclass(frozen=True)
class ModelCallResult:
    output: Any
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
