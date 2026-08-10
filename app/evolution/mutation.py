from dataclasses import dataclass

from app.evolution.specification import StrategySpecification


@dataclass(frozen=True)
class MutationResult:
    specification: StrategySpecification
    mutation_type: str
    changed_fields: list[str]
    memory_ids: list[str]


def mutate_strategy(
    specification: StrategySpecification,
    *,
    generation: int,
    memory_hints: list[dict[str, object]] | None = None,
) -> MutationResult:
    memory_hints = memory_hints or []
    payload = specification.model_dump()
    changed_fields: list[str] = []
    mutation_type = "lookback_adjustment"
    memory_ids = [str(item.get("lesson_id")) for item in memory_hints if item.get("lesson_id")]

    if _memory_mentions(memory_hints, "volatility"):
        payload["position_sizing"] = {
            **payload["position_sizing"],
            "method": "volatility_targeted",
            "target_volatility": 0.15,
        }
        payload["volatility_filter"] = {"enabled": True, "max_realized_volatility": 0.04}
        changed_fields.extend(["position_sizing", "volatility_filter"])
        mutation_type = "memory_volatility_scaling"
    else:
        short_window = int(payload["entry_conditions"]["short_window"])
        long_window = int(payload["entry_conditions"]["long_window"])
        step = 1 + generation % 3
        if generation % 2 == 0:
            short_window = max(2, short_window - step)
        else:
            short_window = min(long_window - 1, short_window + step)
        payload["lookback"] = short_window
        payload["entry_conditions"] = {
            **payload["entry_conditions"],
            "short_window": short_window,
            "long_window": long_window,
        }
        changed_fields.extend(["lookback", "entry_conditions.short_window"])

    return MutationResult(
        specification=StrategySpecification.model_validate(payload),
        mutation_type=mutation_type,
        changed_fields=changed_fields,
        memory_ids=memory_ids,
    )


def crossover(
    left: StrategySpecification,
    right: StrategySpecification,
) -> StrategySpecification | None:
    if left.strategy_family != right.strategy_family or left.signal_type != right.signal_type:
        return None
    payload = left.model_dump()
    payload["exit_conditions"] = right.exit_conditions
    payload["risk_parameters"] = right.risk_parameters
    return StrategySpecification.model_validate(payload)


def _memory_mentions(memory_hints: list[dict[str, object]], term: str) -> bool:
    return any(term in str(item).lower() for item in memory_hints)
