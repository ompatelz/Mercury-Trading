from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class StrategySpecification(BaseModel):
    strategy_family: Literal["moving_average_crossover"] = "moving_average_crossover"
    signal_type: Literal["trend_following"] = "trend_following"
    lookback: int = Field(default=20, ge=2, le=252)
    entry_conditions: dict[str, Any] = Field(default_factory=dict)
    exit_conditions: dict[str, Any] = Field(default_factory=dict)
    position_sizing: dict[str, Any] = Field(
        default_factory=lambda: {"method": "fixed_fraction", "fraction": 1.0}
    )
    volatility_filter: dict[str, Any] = Field(default_factory=lambda: {"enabled": False})
    trend_filter: dict[str, Any] = Field(default_factory=lambda: {"enabled": False})
    risk_parameters: dict[str, Any] = Field(default_factory=lambda: {"max_drawdown": 0.25})
    execution_parameters: dict[str, Any] = Field(
        default_factory=lambda: {"transaction_cost_bps": 1.0, "slippage_bps": 0.0}
    )

    @model_validator(mode="after")
    def validate_moving_average(self) -> "StrategySpecification":
        short_window = int(self.entry_conditions.get("short_window", self.lookback))
        long_window = int(self.entry_conditions.get("long_window", max(self.lookback * 2, 3)))
        if short_window < 2:
            raise ValueError("short_window must be >= 2")
        if long_window <= short_window:
            raise ValueError("long_window must be greater than short_window")
        if long_window > 252:
            raise ValueError("long_window must be <= 252")
        fraction = float(self.position_sizing.get("fraction", 1.0))
        if fraction <= 0.0 or fraction > 1.0:
            raise ValueError("position fraction must be in (0, 1]")
        return self

    @property
    def short_window(self) -> int:
        return int(self.entry_conditions.get("short_window", self.lookback))

    @property
    def long_window(self) -> int:
        return int(self.entry_conditions.get("long_window", max(self.lookback * 2, 3)))


def moving_average_specification(short_window: int, long_window: int) -> StrategySpecification:
    return StrategySpecification(
        lookback=short_window,
        entry_conditions={
            "short_window": short_window,
            "long_window": long_window,
            "signal": "short_ma_crosses_long_ma",
        },
        exit_conditions={"signal": "short_ma_below_long_ma"},
    )


def complexity_score(specification: StrategySpecification) -> tuple[float, dict[str, int]]:
    condition_count = len(specification.entry_conditions) + len(specification.exit_conditions)
    filter_count = int(bool(specification.volatility_filter.get("enabled"))) + int(
        bool(specification.trend_filter.get("enabled"))
    )
    parameter_count = (
        len(specification.position_sizing)
        + len(specification.risk_parameters)
        + len(specification.execution_parameters)
    )
    indicator_count = 2 + filter_count
    score = condition_count + parameter_count * 0.5 + indicator_count + filter_count
    return round(score, 4), {
        "conditions": condition_count,
        "parameters": parameter_count,
        "indicators": indicator_count,
        "filters": filter_count,
    }
