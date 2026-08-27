from pathlib import Path

import polars as pl
import pytest
from sqlalchemy.orm import Session

from app.data.service import DataLineageService, DataQualityError, FeatureStore, data_quality_report
from app.market_data.normalization import normalize_bars
from tests.conftest import sample_raw_bars


def _bars() -> pl.DataFrame:
    return normalize_bars(sample_raw_bars(), symbol="MSFT", interval="1d")


def test_changed_data_creates_immutable_version_and_lineage(
    db_session: Session, tmp_path: Path
) -> None:
    service = DataLineageService(db_session, tmp_path)
    first = service.create_dataset_version(
        name="MSFT_daily", bars=_bars(), provider="test", frequency="1d"
    )
    changed = _bars().with_columns((pl.col("close") + 1).alias("close"))
    second = service.create_dataset_version(
        name="MSFT_daily",
        bars=changed,
        provider="test",
        frequency="1d",
        parent_version_id=first.id,
        transformation="correction",
        parameters={"reason": "provider correction"},
    )

    assert first.version == 1
    assert second.version == 2
    assert (
        service.bars_for_version(first.id).get_column("close").to_list()
        != service.bars_for_version(second.id).get_column("close").to_list()
    )
    assert service.lineage(first.dataset_id)[1].parent_dataset_version_id == first.id


def test_quality_report_rejects_duplicates_and_gaps() -> None:
    duplicated = _bars().vstack(_bars().head(1))
    report = data_quality_report(duplicated, "1d")
    assert report["valid"] is False
    assert any(item["rule"] == "duplicate_timestamps" for item in report["issues"])
    minute = (
        _bars()
        .head(2)
        .with_columns(
            pl.Series(
                "timestamp", ["2024-01-01T00:00:00+00:00", "2024-01-01T00:03:00+00:00"]
            ).str.to_datetime(time_zone="UTC")
        )
    )
    assert any(
        item["rule"] == "unexpected_gaps" for item in data_quality_report(minute, "1m")["issues"]
    )


def test_feature_store_is_deterministic_and_cache_scoped(
    db_session: Session, tmp_path: Path
) -> None:
    lineage = DataLineageService(db_session, tmp_path)
    dataset = lineage.create_dataset_version(
        name="MSFT_daily", bars=_bars(), provider="test", frequency="1d"
    )
    store = FeatureStore(db_session, tmp_path)
    feature = store.register(
        name="moving_average",
        version="v1",
        implementation="rolling_mean_close",
        lookback=3,
        parameters={"window": 3},
    )
    first = store.compute(dataset.id, feature.id)
    second = store.compute(dataset.id, feature.id)

    assert first.equals(second)
    assert (
        db_session.query(
            __import__(
                "app.models.data", fromlist=["FeatureMaterialization"]
            ).FeatureMaterialization
        ).count()
        == 1
    )


def test_unsupported_feature_is_explicit(db_session: Session, tmp_path: Path) -> None:
    lineage = DataLineageService(db_session, tmp_path)
    dataset = lineage.create_dataset_version(
        name="MSFT_daily", bars=_bars(), provider="test", frequency="1d"
    )
    feature = FeatureStore(db_session, tmp_path).register(
        name="bad", version="v1", implementation="unknown", lookback=1
    )
    with pytest.raises(DataQualityError, match="unsupported"):
        FeatureStore(db_session, tmp_path).compute(dataset.id, feature.id)
