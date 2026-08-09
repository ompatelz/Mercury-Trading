from dataclasses import dataclass
from typing import Any

from app.backtesting.strategy import MovingAverageCrossoverStrategy, Strategy


@dataclass(frozen=True)
class StrategyDefinition:
    name: str
    parameter_names: frozenset[str]

    def validate_parameters(self, parameters: dict[str, Any]) -> dict[str, int]:
        unknown = set(parameters) - self.parameter_names
        if unknown:
            raise ValueError(f"unknown parameters for {self.name}: {sorted(unknown)}")

        try:
            fast_window = int(parameters["fast_window"])
            slow_window = int(parameters["slow_window"])
        except KeyError as exc:
            raise ValueError(f"missing required parameter: {exc.args[0]}") from exc

        if fast_window < 2:
            raise ValueError("fast_window must be at least 2")
        if slow_window < 3:
            raise ValueError("slow_window must be at least 3")
        if fast_window >= slow_window:
            raise ValueError("fast_window must be less than slow_window")

        return {"fast_window": fast_window, "slow_window": slow_window}

    def build(self, parameters: dict[str, Any]) -> Strategy:
        validated = self.validate_parameters(parameters)
        return MovingAverageCrossoverStrategy(
            short_window=validated["fast_window"],
            long_window=validated["slow_window"],
        )


STRATEGY_REGISTRY: dict[str, StrategyDefinition] = {
    "moving_average_crossover": StrategyDefinition(
        name="moving_average_crossover",
        parameter_names=frozenset({"fast_window", "slow_window"}),
    )
}


def validate_strategy_spec(strategy_name: str, parameters: dict[str, Any]) -> dict[str, int]:
    definition = STRATEGY_REGISTRY.get(strategy_name)
    if definition is None:
        raise ValueError(f"unknown strategy: {strategy_name}")
    return definition.validate_parameters(parameters)
