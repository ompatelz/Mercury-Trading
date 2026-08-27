from datetime import UTC, date, datetime

import pytest
from sqlalchemy.orm import Session

from app.models.evolution import EvolutionRun, StrategyCandidate
from app.strategy_health.schemas import HealthObservationRequest, HealthState
from app.strategy_health.service import StrategyHealthService, allocation_multiplier


def _strategy(db_session: Session) -> StrategyCandidate:
    run = EvolutionRun(
        objective="Test strategy health lifecycle",
        symbol="MSFT",
        interval="1d",
        status="completed",
        settings={},
        metrics={},
        memory_enabled=False,
        memory_provenance=[],
        report={},
    )
    db_session.add(run)
    db_session.flush()
    candidate = StrategyCandidate(
        evolution_run_id=run.id,
        parent_strategy_ids=[],
        generation=0,
        strategy_specification={},
        mutation_type=None,
        changed_fields=[],
        fitness={},
        regime_performance={},
        diversity={},
        status="evaluated",
        rejection_reason=None,
        promotion_status="promote",
        memory_ids=[],
    )
    db_session.add(candidate)
    db_session.flush()
    return candidate


def _observation(
    *, return_value: float, sharpe: float, trades: int = 12
) -> HealthObservationRequest:
    return HealthObservationRequest(
        observed_at=datetime(2026, 8, 27, tzinfo=UTC),
        metrics={
            "observations": 5,
            "trades": trades,
            "rolling_return": return_value,
            "rolling_sharpe": sharpe,
            "rolling_drawdown": -0.03,
            "rolling_volatility": 0.1,
            "rolling_turnover": 0.2,
        },
        expected_metrics={
            "return": 0.05,
            "sharpe": 1.0,
            "max_drawdown": -0.05,
            "volatility": 0.1,
            "turnover": 0.2,
        },
    )


def test_small_sample_does_not_degrade_or_retire(db_session: Session) -> None:
    candidate = _strategy(db_session)
    health = StrategyHealthService(db_session).record_observation(
        candidate.id, _observation(return_value=-0.2, sharpe=-3.0, trades=2)
    )
    assert health.state == HealthState.HEALTHY
    assert health.lifecycle_state == "RETAIN"


def test_persistent_alpha_decay_becomes_degraded(db_session: Session) -> None:
    candidate = _strategy(db_session)
    service = StrategyHealthService(db_session)
    first = service.record_observation(candidate.id, _observation(return_value=-0.03, sharpe=0.2))
    assert first.state == HealthState.WATCH
    second = service.record_observation(candidate.id, _observation(return_value=-0.03, sharpe=0.2))
    assert second.state == HealthState.DEGRADED
    assert "PERFORMANCE_DEGRADATION" in second.active_flags
    assert second.lifecycle_state == "DE_RISK"


def test_regime_and_execution_do_not_create_alpha_retirement(db_session: Session) -> None:
    candidate = _strategy(db_session)
    request = _observation(return_value=0.05, sharpe=1.0)
    request.regime_context = {"expected_weakness": True}
    request.execution_context = {"expected_cost_bps": 2.0, "realized_cost_bps": 10.0}
    health = StrategyHealthService(db_session).record_observation(candidate.id, request)
    assert health.state == HealthState.WATCH
    assert "REGIME_MISMATCH" in health.active_flags
    assert "EXECUTION_DEGRADATION" in health.active_flags


def test_suspend_reactivate_and_explicit_retirement(db_session: Session) -> None:
    candidate = _strategy(db_session)
    service = StrategyHealthService(db_session)
    service.record_observation(candidate.id, _observation(return_value=0.05, sharpe=1.0))
    assert (
        service.transition(candidate.id, HealthState.SUSPENDED, "data feed unavailable").state
        == "SUSPENDED"
    )
    assert (
        service.transition(candidate.id, HealthState.HEALTHY, "regime recovered").lifecycle_state
        == "ACTIVE"
    )
    assert (
        service.transition(candidate.id, HealthState.RETIRED, "replacement validated").state
        == "RETIRED"
    )
    with pytest.raises(ValueError, match="retired"):
        service.transition(candidate.id, HealthState.HEALTHY, "no automatic reactivation")


def test_periodic_schedule_creates_one_campaign_per_day(db_session: Session) -> None:
    candidate = _strategy(db_session)
    service = StrategyHealthService(db_session)
    service.create_schedule(
        {
            "strategy_id": candidate.id,
            "mode": "PERIODIC",
            "cadence_days": 30,
            "campaign_template": {
                "objective": "Revalidate degraded strategy evidence",
                "symbols": ["MSFT"],
                "start_date": date(2024, 1, 1),
                "end_date": date(2024, 6, 1),
            },
            "trigger_types": [],
        }
    )
    first = service.run_due_schedules(datetime(2026, 8, 27, tzinfo=UTC))
    second = service.run_due_schedules(datetime(2026, 8, 27, tzinfo=UTC))
    assert len(first) == 1
    assert first[0].campaign_id is not None
    assert second == []


def test_portfolio_health_constraints_are_deterministic() -> None:
    assert allocation_multiplier("HEALTHY") == 1.0
    assert allocation_multiplier("DEGRADED") == 0.5
    assert allocation_multiplier("SUSPENDED") == 0.0
