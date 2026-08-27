from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.evolution.diversity import population_diversity
from app.evolution.fitness import champion_decision, fitness_score
from app.evolution.mutation import mutate_strategy
from app.evolution.schemas import EvolutionRunCreateRequest
from app.evolution.specification import StrategySpecification, moving_average_specification
from app.experiments.service import ExperimentService
from app.governance.service import DecisionService
from app.memory.service import ResearchMemoryService
from app.models.evolution import EvolutionRun, StrategyCandidate
from app.schemas.experiment import BacktestRequest


@dataclass(frozen=True)
class _PopulationEntry:
    specification: StrategySpecification
    parent_ids: list[str]
    mutation_type: str | None
    changed_fields: list[str]
    memory_ids: list[str]


class EvolutionService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_run(self, request: EvolutionRunCreateRequest) -> EvolutionRun:
        run = EvolutionRun(
            objective=request.objective,
            symbol=request.symbol.upper(),
            interval=request.interval,
            status="running",
            settings=request.model_dump(mode="json"),
            metrics={},
            memory_enabled=request.memory_enabled,
            memory_provenance=[],
            report={},
        )
        self.session.add(run)
        self.session.flush()
        memory_hints = self._retrieve_memory(request) if request.memory_enabled else []
        run.memory_provenance = memory_hints

        population = [
            _PopulationEntry(
                specification=moving_average_specification(
                    short_window=int(item["short_window"]),
                    long_window=int(item["long_window"]),
                ),
                parent_ids=[],
                mutation_type=None,
                changed_fields=[],
                memory_ids=[],
            )
            for item in request.initial_population[: request.population_size]
        ]
        champion: StrategyCandidate | None = None
        rejected = 0
        for generation in range(request.generations):
            specifications = [item.specification for item in population]
            diversity = population_diversity(specifications)
            candidates = [
                self._evaluate_candidate(
                    run=run,
                    request=request,
                    specification=item.specification,
                    generation=generation,
                    diversity=diversity,
                    parent_ids=item.parent_ids,
                    mutation_type=item.mutation_type,
                    changed_fields=item.changed_fields,
                    memory_ids=item.memory_ids,
                )
                for item in population
            ]
            candidates = sorted(
                candidates, key=lambda item: float(item.fitness["score"]), reverse=True
            )
            best = candidates[0]
            decision = champion_decision(champion.fitness if champion else None, best.fitness)
            best.promotion_status = str(decision["decision"])
            if decision["decision"] == "promote":
                champion = best
            else:
                best.rejection_reason = str(decision["reason"])
                rejected += 1
            DecisionService(self.session).record(
                decision_type="STRATEGY_PROMOTION"
                if decision["decision"] == "promote"
                else "STRATEGY_REJECTION",
                outcome=str(decision["decision"]).upper(),
                actor="EvolutionService",
                reason=str(decision["reason"]),
                strategy_id=best.id,
                correlation_id=str(run.id),
                inputs={
                    "parent_strategy_ids": best.parent_strategy_ids,
                    "mutation_type": best.mutation_type,
                    "changed_fields": best.changed_fields,
                },
                metrics=best.fitness,
                alternatives=[
                    {"strategy_id": str(item.id), "fitness": item.fitness}
                    for item in candidates
                    if item.id != best.id
                ],
                provenance={
                    "evolution_run_id": str(run.id),
                    "memory": run.memory_provenance,
                    "regime_performance": best.regime_performance,
                },
                versions={"fitness": "v1", "strategy_specification": "v1"},
                rules=[
                    {
                        "rule": "CHAMPION_MARGIN",
                        "rule_version": "v1",
                        "threshold": "strict fitness improvement",
                        "observed_value": best.fitness.get("score"),
                        "passed": decision["decision"] == "promote",
                    }
                ],
            )
            parents = candidates[: max(1, min(len(candidates), request.population_size // 2))]
            population = [
                _PopulationEntry(
                    specification=StrategySpecification.model_validate(
                        parent.strategy_specification
                    ),
                    parent_ids=parent.parent_strategy_ids,
                    mutation_type=None,
                    changed_fields=[],
                    memory_ids=parent.memory_ids,
                )
                for parent in parents
            ]
            while len(population) < request.population_size:
                parent = parents[len(population) % len(parents)]
                mutation = mutate_strategy(
                    StrategySpecification.model_validate(parent.strategy_specification),
                    generation=generation + 1,
                    memory_hints=memory_hints,
                )
                population.append(
                    _PopulationEntry(
                        specification=mutation.specification,
                        parent_ids=[str(parent.id)],
                        mutation_type=mutation.mutation_type,
                        changed_fields=mutation.changed_fields,
                        memory_ids=mutation.memory_ids,
                    )
                )

        all_candidates = self.list_candidates(run.id)
        run.status = "completed"
        run.metrics = {
            "generations_completed": request.generations,
            "population_size": request.population_size,
            "candidate_count": len(all_candidates),
            "rejected_candidates": rejected,
            "best_fitness": max(
                (float(candidate.fitness.get("score", 0.0)) for candidate in all_candidates),
                default=0.0,
            ),
            "memory_retrievals": len(memory_hints),
        }
        run.report = _build_evolution_report(run, all_candidates, champion)
        self.session.flush()
        self.session.refresh(run)
        return run

    def get_run(self, run_id: UUID) -> EvolutionRun | None:
        return self.session.get(EvolutionRun, run_id)

    def list_candidates(self, run_id: UUID) -> list[StrategyCandidate]:
        return list(
            self.session.scalars(
                select(StrategyCandidate)
                .where(StrategyCandidate.evolution_run_id == run_id)
                .order_by(StrategyCandidate.generation, StrategyCandidate.created_at)
            )
        )

    def champion(self, run_id: UUID) -> StrategyCandidate | None:
        candidates = self.list_candidates(run_id)
        promoted = [
            candidate for candidate in candidates if candidate.promotion_status == "promote"
        ]
        if not promoted:
            return None
        return max(promoted, key=lambda item: float(item.fitness.get("score", 0.0)))

    def memory_comparison(self, request: EvolutionRunCreateRequest) -> dict[str, object]:
        off = self.create_run(request.model_copy(update={"memory_enabled": False}))
        on = self.create_run(request.model_copy(update={"memory_enabled": True}))
        return {
            "without_memory_run_id": str(off.id),
            "with_memory_run_id": str(on.id),
            "without_memory_best_fitness": off.metrics.get("best_fitness", 0.0),
            "with_memory_best_fitness": on.metrics.get("best_fitness", 0.0),
            "memory_helped": float(on.metrics.get("best_fitness", 0.0))
            > float(off.metrics.get("best_fitness", 0.0)),
            "candidate_count_delta": int(on.metrics.get("candidate_count", 0))
            - int(off.metrics.get("candidate_count", 0)),
        }

    def _evaluate_candidate(
        self,
        *,
        run: EvolutionRun,
        request: EvolutionRunCreateRequest,
        specification: StrategySpecification,
        generation: int,
        diversity: dict[str, float | int],
        parent_ids: list[str],
        mutation_type: str | None,
        changed_fields: list[str],
        memory_ids: list[str],
    ) -> StrategyCandidate:
        experiment = ExperimentService(self.session).run_backtest(
            BacktestRequest(
                symbol=request.symbol,
                start=request.start,
                end=request.end,
                interval=request.interval,
                short_window=specification.short_window,
                long_window=specification.long_window,
                transaction_cost_bps=request.transaction_cost_bps,
                slippage_bps=request.slippage_bps,
            )
        )
        regime_robustness = experiment.run_metadata.get("regime_robustness", {})
        fitness = fitness_score(
            metrics=experiment.metrics,
            evaluation={},
            regime_robustness=regime_robustness,
            specification=specification,
            risk_flags=[],
        )
        candidate = StrategyCandidate(
            evolution_run_id=run.id,
            parent_strategy_ids=parent_ids,
            generation=generation,
            strategy_specification=specification.model_dump(mode="json"),
            mutation_type=mutation_type,
            changed_fields=changed_fields,
            fitness=fitness,
            regime_performance=experiment.run_metadata.get("regime_performance", {}),
            diversity=diversity,
            status="evaluated",
            rejection_reason=None,
            promotion_status="challenger",
            memory_ids=memory_ids,
        )
        self.session.add(candidate)
        self.session.flush()
        if mutation_type:
            DecisionService(self.session).record(
                decision_type="MUTATION_SELECTION",
                outcome="SELECTED",
                actor="EvolutionService",
                reason="Candidate mutation was selected for deterministic backtest evaluation.",
                strategy_id=candidate.id,
                correlation_id=str(run.id),
                inputs={"mutation_type": mutation_type, "changed_fields": changed_fields},
                metrics=candidate.fitness,
                provenance={
                    "parent_strategy_ids": parent_ids,
                    "memory_ids": memory_ids,
                    "memory_retrieval": run.memory_provenance,
                },
                versions={"mutation": "v1", "fitness": "v1"},
            )
        return candidate

    def _retrieve_memory(self, request: EvolutionRunCreateRequest) -> list[dict[str, object]]:
        return [
            {
                "lesson_id": str(item.lesson_id),
                "source_experiment_id": str(item.source_experiment_id),
                "similarity": item.similarity,
                "summary": item.summary,
                "tags": item.tags,
                "influence": "available_to_mutation",
            }
            for item in ResearchMemoryService(self.session).retrieve_for_research(
                request.objective,
                request.symbol,
                strategy_family="moving_average_crossover",
            )
        ]


def _build_evolution_report(
    run: EvolutionRun,
    candidates: list[StrategyCandidate],
    champion: StrategyCandidate | None,
) -> dict[str, object]:
    fitness_values = [float(candidate.fitness.get("score", 0.0)) for candidate in candidates]
    return {
        "research_objective": run.objective,
        "initial_population": run.settings.get("initial_population", []),
        "generations": run.settings.get("generations"),
        "mutations_attempted": sum(1 for candidate in candidates if candidate.mutation_type),
        "strategies_rejected": [
            str(candidate.id) for candidate in candidates if candidate.rejection_reason
        ],
        "fitness_progression": fitness_values,
        "population_diversity": [candidate.diversity for candidate in candidates],
        "regime_performance": {
            str(candidate.id): candidate.regime_performance for candidate in candidates
        },
        "champion": str(champion.id) if champion else None,
        "memory_retrieved": run.memory_provenance,
        "memory_improved_search": "compare via /evolution-runs/memory-comparison",
        "unresolved_weaknesses": sorted(
            {
                flag
                for candidate in candidates
                for flag in candidate.fitness.get("penalty_flags", [])
            }
        ),
    }
