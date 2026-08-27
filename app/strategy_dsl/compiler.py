from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

import polars as pl

from app.strategy_dsl.schemas import COMPILER_VERSION, ComparisonCondition, Condition, StrategySpec
from app.strategy_dsl.validation import StrategyValidationError, complexity_score, validate_strategy


@dataclass(frozen=True)
class ExecutionPlan:
    compiler_version: str
    strategy_hash: str
    complexity: int
    steps: tuple[str, ...]


def canonical_json(spec: StrategySpec) -> str:
    return json.dumps(spec.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def strategy_hash(spec: StrategySpec) -> str:
    return hashlib.sha256(canonical_json(spec).encode("utf-8")).hexdigest()


def compile_strategy(spec: StrategySpec) -> ExecutionPlan:
    validate_strategy(spec)
    steps = tuple(
        [
            f"compute {name}=SMA(close,{indicator.window})"
            for name, indicator in sorted(spec.indicators.items())
        ]
        + [f"evaluate entry: {_describe_condition(spec.entry)}"]
        + [f"evaluate exit: {_describe_condition(spec.exit)}"]
        + [f"position size: {spec.position_sizing.value:.2%} equity", "execute on next bar open"]
    )
    return ExecutionPlan(COMPILER_VERSION, strategy_hash(spec), complexity_score(spec), steps)


def explain_strategy(spec: StrategySpec) -> str:
    plan = compile_strategy(spec)
    indicator_lines = ", ".join(
        f"{name}: {item.window}-bar SMA" for name, item in sorted(spec.indicators.items())
    )
    return (
        f"Momentum strategy using {indicator_lines}. Enter when {_describe_condition(spec.entry)}. "
        f"Exit when {_describe_condition(spec.exit)}. "
        f"Use {spec.position_sizing.value:.0%} of equity. "
        f"Complexity {plan.complexity}; hash {plan.strategy_hash}."
    )


def evaluate_positions(spec: StrategySpec, bars: pl.DataFrame) -> pl.DataFrame:
    """Compile to Polars expressions. No future-bar operator exists in the DSL."""
    validate_strategy(spec)
    if bars.height > spec.risk_constraints.max_bars_processed:
        raise StrategyValidationError(("bar count exceeds risk_constraints.max_bars_processed",))
    frame = bars
    for name, indicator in spec.indicators.items():
        frame = frame.with_columns(pl.col("close").rolling_mean(indicator.window).alias(name))
    entry = _condition_expression(spec.entry)
    exit = _condition_expression(spec.exit)
    allowed = pl.lit(True)
    for condition in spec.filters:
        allowed = allowed & _condition_expression(condition)
    # Signals are deliberately shifted once: a completed bar can only trade at the next open.
    return frame.with_columns(
        pl.when((entry & allowed).fill_null(False))
        .then(spec.position_sizing.value)
        .when(exit.fill_null(False))
        .then(0.0)
        .otherwise(None)
        .forward_fill()
        .fill_null(0.0)
        .shift(1)
        .fill_null(0.0)
        .alias("position")
    )


def _condition_expression(condition: Condition) -> pl.Expr:
    if isinstance(condition, ComparisonCondition):
        left, right = pl.col(condition.left), pl.col(condition.right)
        comparisons = {
            "gt": left > right,
            "gte": left >= right,
            "lt": left < right,
            "lte": left <= right,
        }
        return comparisons[condition.operator]
    expressions = [_condition_expression(item) for item in condition.conditions]
    result = expressions[0]
    for expression in expressions[1:]:
        result = result & expression if condition.type == "all" else result | expression
    return result


def _describe_condition(condition: Condition) -> str:
    if isinstance(condition, ComparisonCondition):
        symbols = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}
        return f"{condition.left} {symbols[condition.operator]} {condition.right}"
    joiner = " and " if condition.type == "all" else " or "
    return "(" + joiner.join(_describe_condition(item) for item in condition.conditions) + ")"
