from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.alternative_data.alignment import align_asof
from app.alternative_data.features import (
    correlation,
    cross_sectional_rank,
    relative_strength,
    yield_curve_slope,
)
from app.alternative_data.schemas import (
    AlignmentPolicy,
    Asset,
    AssetClass,
    TimedObservation,
    UniverseDefinition,
)
from app.alternative_data.service import AlternativeDataService, DataAvailabilityError


def at(day: int) -> datetime:
    return datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=day - 1)


def test_alignment_blocks_future_macro_release_and_marks_stale_values() -> None:
    cpi = TimedObservation("CPI", at(1), at(10), 3.1, source_release_id="cpi-jan")
    aligned = align_asof(
        targets=[at(5), at(10), at(20)],
        observations=[cpi],
        policy=AlignmentPolicy(max_staleness=timedelta(days=5)),
    )

    assert [item.status for item in aligned] == ["unavailable", "stale", "stale"]
    assert aligned[0].value is None
    assert aligned[1].available_at == at(10)


def test_alignment_uses_only_latest_available_fundamental_release() -> None:
    observations = [
        TimedObservation("earnings", at(31), at(40), 1.0, asset_id="asset:acme"),
        TimedObservation("earnings", at(61), at(70), 2.0, asset_id="asset:acme"),
    ]
    aligned = align_asof(
        targets=[at(50), at(65)], observations=observations, policy=AlignmentPolicy()
    )
    assert [item.value for item in aligned] == [1.0, 1.0]


def test_cross_asset_features_are_deterministic_and_explicit() -> None:
    assert relative_strength([120, 150], [100, 125]) == [1.2, 1.2]
    assert cross_sectional_rank({"BOND": 0.1, "EQUITY": 0.1, "GOLD": 0.2}) == {
        "GOLD": 1,
        "BOND": 2,
        "EQUITY": 3,
    }
    assert correlation([1, 2, 3], [2, 4, 6]) == pytest.approx(1.0)
    assert yield_curve_slope(4.0, 4.5) == 0.5


def test_asset_universe_is_versioned_and_catalog_marks_survivorship_risk(
    db_session: Session,
) -> None:
    service = AlternativeDataService(db_session)
    service.register_asset(
        Asset("asset:spy", "SPY", AssetClass.ETF, "USD", "America/New_York", "ARCX")
    )
    service.register_universe(
        UniverseDefinition(
            name="US_LIQUID_ETFS",
            version="v1",
            membership=("asset:spy",),
            effective_from=at(1),
            filters={"minimum_dollar_volume": 1_000_000},
            survivorship_bias_risk=True,
        )
    )
    catalog = service.catalog()
    assert catalog["universes"][0]["limitations"] == ["SURVIVORSHIP_BIAS_RISK"]


def test_campaign_input_validation_does_not_advertise_unpersisted_providers(
    db_session: Session,
) -> None:
    with pytest.raises(DataAvailabilityError, match="unavailable"):
        AlternativeDataService(db_session).require_available_inputs(["macro-provider"])
