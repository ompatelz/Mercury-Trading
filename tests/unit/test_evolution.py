from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from app.evolution.fitness import champion_decision, fitness_score
from app.evolution.mutation import crossover, mutate_strategy
from app.evolution.schemas import EvolutionRunCreateRequest
from app.evolution.service import EvolutionService
from app.evolution.specification import moving_average_specification
from app.models.market_data import MarketBar


def test_strategy_specification_mutation_and_crossover_are_bounded() -> None:
    left = moving_average_specification(5, 20)
    right = moving_average_specification(10, 30)

    mutation = mutate_strategy(left, generation=1)
    child = crossover(left, right)

    assert mutation.specification.short_window < mutation.specification.long_window
    assert mutation.changed_fields
    assert child is not None
    assert child.strategy_family == left.strategy_family


def test_memory_hint_influences_mutation_and_preserves_provenance() -> None:
    spec = moving_average_specification(10, 30)
    mutation = mutate_strategy(
        spec,
        generation=1,
        memory_hints=[{"lesson_id": "lesson-1", "summary": "volatility scaling helped"}],
    )

    assert mutation.mutation_type == "memory_volatility_scaling"
    assert mutation.specification.volatility_filter["enabled"] is True
    assert mutation.memory_ids == ["lesson-1"]


def test_fitness_penalizes_complexity_and_champion_requires_margin() -> None:
    spec = moving_average_specification(5, 20)
    fitness = fitness_score(
        metrics={
            "sharpe_ratio": 1.0,
            "sortino_ratio": 1.2,
            "max_drawdown": -0.1,
            "turnover": 1.0,
            "number_of_trades": 5,
        },
        evaluation={"walk_forward": {"consistency": 0.8}},
        regime_robustness={"score": 75.0, "flags": []},
        specification=spec,
        risk_flags=[],
    )
    decision = champion_decision({"score": 60.0}, fitness)

    assert fitness["score"] > 60.0
    assert fitness["complexity_score"] > 0.0
    assert decision["decision"] == "promote"


def test_evolution_run_persists_lineage_and_report(db_session: Session) -> None:
    _seed_bars(db_session, days=60)
    request = EvolutionRunCreateRequest(
        objective="Find robust moving average variants for MSFT",
        symbol="MSFT",
        start=datetime(2024, 1, 1).date(),
        end=datetime(2024, 3, 1).date(),
        initial_population=[
            {"short_window": 3, "long_window": 8},
            {"short_window": 5, "long_window": 12},
        ],
        generations=2,
        population_size=2,
    )

    run = EvolutionService(db_session).create_run(request)

    candidates = EvolutionService(db_session).list_candidates(run.id)
    assert run.status == "completed"
    assert candidates
    assert run.report["research_objective"] == request.objective
    assert any(candidate.generation == 1 for candidate in candidates)
    assert all(candidate.strategy_specification["strategy_family"] for candidate in candidates)


def _seed_bars(session: Session, days: int) -> None:
    start = datetime(2024, 1, 1)
    rows = []
    for index in range(days):
        price = 100 + index * 0.5 + (index % 7) * 0.2
        rows.append(
            MarketBar(
                symbol="MSFT",
                timestamp=start + timedelta(days=index),
                interval="1d",
                open=Decimal(str(price)),
                high=Decimal(str(price + 1)),
                low=Decimal(str(price - 1)),
                close=Decimal(str(price + 0.2)),
                volume=1_000 + index,
            )
        )
    session.add_all(rows)
    session.flush()
