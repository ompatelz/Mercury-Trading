from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.strategy_dsl.schemas import ComparisonCondition, Condition, LogicalCondition, StrategySpec


@dataclass(frozen=True)
class StrategyValidationError(ValueError):
    errors: tuple[str, ...]

    def __str__(self) -> str:
        return "; ".join(self.errors)


def parse_strategy(payload: dict[str, Any]) -> StrategySpec:
    try:
        return StrategySpec.model_validate(payload)
    except ValidationError as exc:
        raise StrategyValidationError(
            tuple(_format_error(dict(item)) for item in exc.errors())
        ) from exc


def validate_strategy(spec: StrategySpec) -> StrategySpec:
    errors: list[str] = []
    _validate_condition(spec.entry, "entry", spec, errors)
    _validate_condition(spec.exit, "exit", spec, errors)
    for index, condition in enumerate(spec.filters):
        _validate_condition(condition, f"filters[{index}]", spec, errors)
    if spec.entry == spec.exit:
        errors.append("entry and exit conditions cannot be identical")
    _validate_crossover_windows(spec, errors)
    if len(spec.indicators) > spec.risk_constraints.max_indicator_count:
        errors.append("indicator count exceeds risk_constraints.max_indicator_count")
    if complexity_score(spec) > spec.risk_constraints.max_rule_complexity:
        errors.append("rule complexity exceeds risk_constraints.max_rule_complexity")
    if errors:
        raise StrategyValidationError(tuple(errors))
    return spec


def complexity_score(spec: StrategySpec) -> int:
    return (
        len(spec.indicators) * 2
        + _condition_complexity(spec.entry)
        + _condition_complexity(spec.exit)
        + sum(_condition_complexity(item) for item in spec.filters)
    )


def _validate_condition(
    condition: Condition, path: str, spec: StrategySpec, errors: list[str]
) -> None:
    if isinstance(condition, ComparisonCondition):
        for side, reference in (("left", condition.left), ("right", condition.right)):
            if reference not in spec.indicators:
                errors.append(f"{path}.{side} references unknown indicator '{reference}'")
        if condition.left == condition.right:
            errors.append(f"{path} cannot compare an indicator to itself")
        return
    if isinstance(condition, LogicalCondition):
        for index, child in enumerate(condition.conditions):
            _validate_condition(child, f"{path}.conditions[{index}]", spec, errors)


def _condition_complexity(condition: Condition) -> int:
    if isinstance(condition, ComparisonCondition):
        return 1
    return 1 + sum(_condition_complexity(item) for item in condition.conditions)


def _validate_crossover_windows(spec: StrategySpec, errors: list[str]) -> None:
    """Reject the unsupported/inverted MA-crossover interpretation in DSL v1."""
    if not isinstance(spec.entry, ComparisonCondition) or not isinstance(
        spec.exit, ComparisonCondition
    ):
        return
    is_crossover = (
        spec.entry.left == spec.exit.left
        and spec.entry.right == spec.exit.right
        and spec.entry.operator in {"gt", "gte"}
        and spec.exit.operator in {"lt", "lte"}
    )
    if is_crossover and (
        spec.entry.left in spec.indicators
        and spec.entry.right in spec.indicators
        and spec.indicators[spec.entry.left].window >= spec.indicators[spec.entry.right].window
    ):
        errors.append("entry indicator window must be less than exit comparison indicator window")


def _format_error(error: dict[str, Any]) -> str:
    location = ".".join(str(value) for value in error["loc"])
    return f"{location}: {error['msg']}"
