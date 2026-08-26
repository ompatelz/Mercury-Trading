"""Small deterministic research-workflow benchmark suite.

Fixtures describe observable constraints, not a preferred prose response. This
keeps CI independent of a paid model and permits a real-model executor to use
the identical suite outside CI.
"""

from dataclasses import dataclass
from typing import Any

DEFAULT_BENCHMARK_NAME = "research_workflow_core"
DEFAULT_BENCHMARK_VERSION = "v1"


@dataclass(frozen=True)
class BenchmarkTask:
    task_id: str
    task_type: str
    input: dict[str, Any]
    expected_constraints: dict[str, Any]
    scoring_rules: tuple[str, ...]
    fixtures: dict[str, Any]
    metadata: dict[str, Any]
    critical: bool = False


DEFAULT_BENCHMARK_TASKS: tuple[BenchmarkTask, ...] = (
    BenchmarkTask(
        "momentum_strategy",
        "strategy_generation",
        {"objective": "Generate a valid momentum strategy", "symbol": "SPY"},
        {"structured": True, "strategy": "moving_average_crossover"},
        ("structured_output", "strategy_schema_valid", "task_success"),
        {"approved_strategies": ["moving_average_crossover"]},
        {"family": "momentum"},
        True,
    ),
    BenchmarkTask(
        "mean_reversion_strategy",
        "strategy_generation",
        {"objective": "Generate a valid mean-reversion strategy", "symbol": "BTC"},
        {"structured": True, "strategy": "moving_average_crossover"},
        ("structured_output", "strategy_schema_valid", "task_success"),
        {"approved_strategies": ["moving_average_crossover"]},
        {"family": "mean_reversion"},
    ),
    BenchmarkTask(
        "impossible_strategy_rejection",
        "invalid_strategy_rejection",
        {"strategy": "future_close_oracle", "claim": "guaranteed profit"},
        {"reject": True, "failure_type": "invalid_strategy"},
        ("structured_output", "invalid_strategy_rejected", "task_success"),
        {"approved_strategies": ["moving_average_crossover"]},
        {"safety": "unsupported strategy"},
        True,
    ),
    BenchmarkTask(
        "lookahead_bias",
        "bias_detection",
        {"rule": "buy when tomorrow close exceeds today close"},
        {"reject": True, "failure_type": "lookahead_bias"},
        ("structured_output", "lookahead_detected", "task_success"),
        {"future_field": "tomorrow close"},
        {"safety": "no look-ahead"},
        True,
    ),
    BenchmarkTask(
        "overfitting_detection",
        "critique",
        {"evidence": "one winning period after 400 parameter trials"},
        {"failure_type": "overfitting", "mentions_oos": True},
        ("structured_output", "overfitting_detected", "task_success"),
        {"minimum_oos_periods": 1},
        {"quality": "generalization"},
    ),
    BenchmarkTask(
        "failed_experiment_critique",
        "critique",
        {"metrics": {"sharpe_ratio": -0.4, "max_drawdown": -0.31}},
        {"mentions_drawdown": True, "suggests_next_experiment": True},
        ("structured_output", "critique_grounded", "task_success"),
        {"metrics_are_measured": True},
        {"quality": "grounded_critique"},
    ),
    BenchmarkTask(
        "memory_retrieval_relevance",
        "memory_retrieval",
        {"query": "avoid previously rejected SPY momentum parameters"},
        {"retrieved_lesson_id": "lesson-spy-failure", "irrelevant_retrieval": False},
        ("memory_retrieval_relevance", "tool_use_correct", "task_success"),
        {
            "lessons": [
                {"id": "lesson-spy-failure", "tags": ["SPY", "momentum", "failure"]},
                {"id": "lesson-btc", "tags": ["BTC", "mean_reversion"]},
            ]
        },
        {"memory": "failure-aware"},
    ),
    BenchmarkTask(
        "next_experiment_selection",
        "orchestration",
        {"state": "failed single-symbol backtest with no walk-forward validation"},
        {"next_action": "walk_forward_validation"},
        ("structured_output", "workflow_action_valid", "task_success"),
        {"allowed_actions": ["walk_forward_validation", "reject_strategy"]},
        {"workflow": "bounded"},
    ),
)


def get_benchmark(name: str) -> tuple[BenchmarkTask, ...]:
    if name == "research_agent_v1":
        return DEFAULT_BENCHMARK_TASKS
    if name != DEFAULT_BENCHMARK_NAME:
        raise ValueError(f"unknown benchmark: {name}")
    return DEFAULT_BENCHMARK_TASKS
