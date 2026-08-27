from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FactorDefinition(BaseModel):
    """Versioned, interpretable inputs to the factor engine; never executable code."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    factor_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=32)
    input_features: tuple[str, ...] = Field(min_length=1)
    lookback: int = Field(ge=1, le=2_520)
    transformation: Literal["raw", "trailing_return", "inverse_trailing_volatility"]
    ranking_method: Literal["raw", "percentile", "zscore"] = "percentile"
    direction: Literal["high", "low"] = "high"
    universe_requirements: dict[str, str | float | int] = Field(default_factory=dict)
    preprocessing_version: str = "factor-preprocessing-v1"


class FactorStrategySpec(BaseModel):
    """The cross-sectional DSL: universe -> factor -> rank -> select -> weight -> rebalance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dsl_version: Literal["factor-v1"] = "factor-v1"
    universe_id: str = Field(min_length=1)
    factors: tuple[FactorDefinition, ...] = Field(min_length=1, max_length=8)
    factor_weights: dict[str, float] = Field(default_factory=dict)
    selection: Literal["top_n", "top_bottom_quantile"] = "top_n"
    top_n: int | None = Field(default=None, ge=1)
    quantile: float | None = Field(default=None, gt=0.0, le=0.5)
    weighting: Literal["equal_weight", "score_weight", "inverse_volatility"] = "equal_weight"
    rebalance_frequency: Literal["daily", "weekly", "monthly"] = "monthly"
    neutralization: Literal["none", "sector", "size"] = "none"
    transaction_cost_bps: float = Field(default=0.0, ge=0.0)

    @model_validator(mode="after")
    def selection_is_complete(self) -> FactorStrategySpec:
        ids = [factor.factor_id for factor in self.factors]
        if len(ids) != len(set(ids)):
            raise ValueError("factor ids must be unique")
        if self.selection == "top_n" and self.top_n is None:
            raise ValueError("top_n selection requires top_n")
        if self.selection == "top_bottom_quantile" and self.quantile is None:
            raise ValueError("top_bottom_quantile selection requires quantile")
        unknown = set(self.factor_weights) - set(ids)
        if unknown:
            raise ValueError(f"factor_weights reference unknown factors: {sorted(unknown)}")
        return self


class ScorePoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    timestamp: datetime
    asset_id: str
    score: float | None = None
    sector: str | None = None
    size: float | None = None
    volatility: float | None = None


class ForwardReturn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    timestamp: datetime
    asset_id: str
    horizon: int = Field(ge=1)
    value: float
