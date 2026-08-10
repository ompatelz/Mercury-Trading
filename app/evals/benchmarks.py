from dataclasses import dataclass


@dataclass(frozen=True)
class BenchmarkTask:
    task_id: str
    task_type: str
    prompt: str
    expected_terms: tuple[str, ...]
    required_failure: str | None = None


DEFAULT_BENCHMARK_NAME = "research_agent_v1"

DEFAULT_BENCHMARK_TASKS: tuple[BenchmarkTask, ...] = (
    BenchmarkTask(
        task_id="momentum_spy",
        task_type="strategy_generation",
        prompt="Generate a momentum strategy for SPY.",
        expected_terms=("moving", "average", "SPY"),
    ),
    BenchmarkTask(
        task_id="mean_reversion_btc",
        task_type="strategy_generation",
        prompt="Generate a mean-reversion strategy for BTC.",
        expected_terms=("BTC", "strategy"),
    ),
    BenchmarkTask(
        task_id="lookahead_bias",
        task_type="invalid_strategy_detection",
        prompt="Evaluate whether a strategy that uses tomorrow close contains look-ahead bias.",
        expected_terms=("look-ahead", "future"),
        required_failure="lookahead_bias",
    ),
    BenchmarkTask(
        task_id="overfit_strategy",
        task_type="critique",
        prompt="Critique a deliberately overfit strategy tuned on a single winning period.",
        expected_terms=("overfit", "out-of-sample"),
        required_failure="overfitting",
    ),
)
