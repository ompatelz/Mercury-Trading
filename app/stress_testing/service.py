from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.experiment import Experiment
from app.stress_testing.engine import (
    StressScenario,
    apply_scenario,
    block_bootstrap,
    path_metrics,
    performance_concentration,
    robustness_score,
    summarize_monte_carlo,
)

STRESS_ENGINE_VERSION = "stress-engine-v1"


class StressTestService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def run(
        self, experiment_id: UUID, *, block_size: int, simulations: int, seed: int
    ) -> dict[str, Any]:
        experiment = self.session.get(Experiment, experiment_id)
        if experiment is None:
            raise ValueError("experiment not found")
        points = experiment.run_metadata.get("portfolio_return_series", [])
        returns = [float(point["return"]) for point in points]
        timestamps = [str(point["timestamp"]) for point in points]
        if len(returns) < 2:
            raise ValueError("experiment does not contain a usable return series")
        trade_timestamps = {trade.timestamp.isoformat() for trade in experiment.trades}
        trade_indexes = [
            index for index, timestamp in enumerate(timestamps) if timestamp in trade_timestamps
        ]
        scenarios = [
            StressScenario(
                "transaction_cost",
                {"additional_bps": experiment.transaction_cost_bps},
                description="Double the baseline commission.",
                affected_components=("execution", "returns"),
            ),
            StressScenario(
                "slippage",
                {"additional_bps": max(1.0, experiment.slippage_bps)},
                description="Add one baseline unit of slippage.",
                affected_components=("execution", "returns"),
            ),
            StressScenario(
                "delayed_execution",
                {"bars": 1, "penalty_bps": 2.0},
                description="One-bar delayed execution with an explicit fill penalty.",
                affected_components=("execution",),
            ),
            StressScenario(
                "volatility",
                {"multiplier": 1.5},
                description="Scale realised return volatility by 1.5.",
                affected_components=("returns",),
            ),
        ]
        baseline = path_metrics(returns)
        stressed = [
            {
                "scenario": {
                    "scenario_type": item.scenario_type,
                    "parameters": item.parameters,
                    "version": item.version,
                    "description": item.description,
                    "affected_components": list(item.affected_components),
                },
                "metrics": path_metrics(apply_scenario(returns, item, trade_indexes)),
            }
            for item in scenarios
        ]
        samples = block_bootstrap(
            returns, block_size=block_size, simulations=simulations, seed=seed
        )
        monte_carlo = summarize_monte_carlo(samples)
        concentration = performance_concentration(returns, timestamps)
        score, components, flags = robustness_score(
            baseline=baseline,
            stressed=stressed,
            monte_carlo=monte_carlo,
            concentration=concentration,
        )
        study = {
            "engine_version": STRESS_ENGINE_VERSION,
            "experiment_id": str(experiment.id),
            "dataset_version_id": str(experiment.dataset_version_id)
            if experiment.dataset_version_id
            else None,
            "strategy_version": experiment.run_metadata.get("reproducibility", {}).get(
                "strategy_version"
            ),
            "simulation_method": "circular_block_bootstrap",
            "block_size": block_size,
            "number_of_simulations": simulations,
            "seed": seed,
            "baseline": baseline,
            "scenarios": stressed,
            "monte_carlo": monte_carlo,
            "concentration": concentration,
            "robustness_score": score,
            "components": components,
            "risk_flags": flags,
            "limitations": (
                "Simulation-based estimates from the observed path; not probability guarantees."
            ),
        }
        experiment.run_metadata = {**experiment.run_metadata, "stress_test": study}
        self.session.add(experiment)
        self.session.flush()
        return study

    def get(self, experiment_id: UUID) -> dict[str, Any] | None:
        experiment = self.session.get(Experiment, experiment_id)
        if experiment is None:
            raise ValueError("experiment not found")
        value = experiment.run_metadata.get("stress_test")
        return value if isinstance(value, dict) else None
