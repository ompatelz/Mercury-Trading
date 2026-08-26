from datetime import datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.campaigns.optimization import ParameterSpace, generate_parameter_variants
from app.campaigns.schemas import OptimizationStudyCreateRequest
from app.campaigns.service import CampaignService
from app.campaigns.study_service import OptimizationStudyService
from app.models.market_data import MarketBar


def test_structured_parameter_space_supports_all_declared_types_and_constraints() -> None:
    space = ParameterSpace.from_raw(
        {
            "lookback": {"type": "integer", "min": 2, "max": 4},
            "threshold": {"type": "float", "min": 0.5, "max": 1.0, "step": 0.5},
            "exit_method": {"type": "categorical", "values": ["fixed", "trailing"]},
            "use_filter": {"type": "boolean"},
        }
    )

    candidates = space.candidates()

    assert len(candidates) == 24
    assert {item["use_filter"] for item in candidates} == {False, True}
    assert generate_parameter_variants(
        {"short_window": [2, 5], "long_window": [3, 8]}, "random", 3, seed=9
    ) == generate_parameter_variants(
        {"short_window": [2, 5], "long_window": [3, 8]}, "random", 3, seed=9
    )
    assert space.rejection_reasons({"unknown": 1}) == []


def test_optimization_study_uses_campaign_workers_and_never_unlocked_test_data(
    db_session: Session,
) -> None:
    _seed_bars(db_session)
    service = OptimizationStudyService(db_session)
    study = service.create(
        OptimizationStudyCreateRequest(
            objective="Find stable moving-average settings without test-set leakage.",
            symbols=["MSFT"],
            start_date=datetime(2024, 1, 1).date(),
            end_date=datetime(2024, 2, 15).date(),
            trial_budget=2,
            parameter_space={
                "short_window": {"type": "integer", "min": 2, "max": 3},
                "long_window": {"type": "integer", "min": 5, "max": 8, "step": 3},
            },
        )
    )
    study = service.run(study.id)
    while CampaignService(db_session).process_next_job("optimization-test") is not None:
        pass
    db_session.flush()

    trials = service.list_trials(study.id)

    assert len(trials) == 2
    assert {trial.status for trial in trials} <= {"VALID", "REJECTED"}
    assert all(
        trial.objective_components["test_set_used_for_optimization"] is False for trial in trials
    )
    assert all(trial.experiment_id is not None for trial in trials)
    assert service.get(study.id).status == "COMPLETED"  # type: ignore[union-attr]


def test_optimization_study_api_exposes_persisted_study_and_trials(client: TestClient) -> None:
    response = client.post(
        "/optimization/studies",
        json={
            "objective": "Find robust parameters with explicit validation discipline.",
            "symbols": ["MSFT"],
            "start_date": "2024-01-01",
            "end_date": "2024-02-15",
            "trial_budget": 1,
            "parameter_space": {"short_window": [2], "long_window": [5]},
        },
    )

    assert response.status_code == 201
    study = response.json()
    assert study["validation_configuration"]["test"]
    assert (
        client.get(f"/optimization/studies/{study['id']}/trials").json()[0]["status"] == "PENDING"
    )


def _seed_bars(session: Session) -> None:
    start = datetime(2024, 1, 1)
    session.add_all(
        [
            MarketBar(
                symbol="MSFT",
                timestamp=start + timedelta(days=index),
                interval="1d",
                open=Decimal(str(100 + index)),
                high=Decimal(str(101 + index)),
                low=Decimal(str(99 + index)),
                close=Decimal(str(100.5 + index)),
                volume=1_000,
            )
            for index in range(50)
        ]
    )
    session.flush()
