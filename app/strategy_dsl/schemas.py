from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DSL_VERSION = "v1"
COMPILER_VERSION = "strategy-dsl-compiler-v1"


class IndicatorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["sma"]
    window: int = Field(ge=2, le=500)


class ComparisonCondition(BaseModel):
    """A comparison can reference only a named indicator, never a market-data index."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["comparison"] = "comparison"
    left: str = Field(min_length=1, max_length=64)
    operator: Literal["gt", "gte", "lt", "lte"]
    right: str = Field(min_length=1, max_length=64)


class LogicalCondition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["all", "any"]
    conditions: list[Condition] = Field(min_length=2, max_length=8)


Condition = Annotated[ComparisonCondition | LogicalCondition, Field(discriminator="type")]
LogicalCondition.model_rebuild()


class PositionSizing(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: Literal["percent_equity"] = "percent_equity"
    value: float = Field(gt=0.0, le=1.0)


class RiskConstraints(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    max_bars_processed: int = Field(default=100_000, ge=1, le=1_000_000)
    max_runtime_ms: int = Field(default=5_000, ge=1, le=60_000)
    max_indicator_count: int = Field(default=16, ge=1, le=64)
    max_rule_complexity: int = Field(default=32, ge=1, le=128)


class StrategySpec(BaseModel):
    """The entire executable language accepted from an agent in DSL v1."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dsl_version: Literal["v1"] = "v1"
    family: Literal["momentum"] = "momentum"
    indicators: dict[str, IndicatorSpec] = Field(min_length=2, max_length=16)
    entry: Condition
    exit: Condition
    position_sizing: PositionSizing
    filters: list[Condition] = Field(default_factory=list, max_length=8)
    risk_constraints: RiskConstraints = Field(default_factory=RiskConstraints)

    @model_validator(mode="after")
    def indicator_names_are_safe(self) -> StrategySpec:
        for name in self.indicators:
            if not name.replace("_", "").isalnum() or name[0].isdigit():
                raise ValueError("indicator names must be identifiers")
        return self


def moving_average_crossover_spec(parameters: Mapping[str, int | float]) -> StrategySpec:
    """Compatibility adapter for existing Mercury request surfaces.

    It is intentionally the only bridge from legacy name/parameter requests;
    callers cannot supply code or a dataframe expression through this path.
    """
    return StrategySpec(
        indicators={
            "fast_ma": IndicatorSpec(type="sma", window=int(parameters["fast_window"])),
            "slow_ma": IndicatorSpec(type="sma", window=int(parameters["slow_window"])),
        },
        entry=ComparisonCondition(left="fast_ma", operator="gt", right="slow_ma"),
        exit=ComparisonCondition(left="fast_ma", operator="lt", right="slow_ma"),
        position_sizing=PositionSizing(value=1.0),
    )
