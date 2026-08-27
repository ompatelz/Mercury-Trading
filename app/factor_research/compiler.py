from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from app.factor_research.schemas import FactorStrategySpec


@dataclass(frozen=True)
class FactorExecutionPlan:
    compiler_version: str
    strategy_hash: str
    steps: tuple[str, ...]


def compile_factor_strategy(spec: FactorStrategySpec) -> FactorExecutionPlan:
    """Make the restricted cross-sectional DSL auditable before it is evaluated."""
    payload = json.dumps(spec.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    factor_steps = tuple(
        f"compute {item.factor_id}@{item.version}: {item.transformation} lookback={item.lookback}"
        for item in spec.factors
    )
    select = f"select {spec.selection}"
    if spec.selection == "top_n":
        select += f"={spec.top_n}"
    else:
        select += f"={spec.quantile:.0%}" if spec.quantile is not None else ""
    return FactorExecutionPlan(
        "factor-dsl-compiler-v1",
        digest,
        (
            f"universe {spec.universe_id}",
            *factor_steps,
            "rank point-in-time",
            select,
            f"weight {spec.weighting}",
            f"neutralize {spec.neutralization}",
            f"rebalance {spec.rebalance_frequency}",
        ),
    )
