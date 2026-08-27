from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import polars as pl
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.data import (
    Dataset,
    DatasetLineage,
    DatasetSnapshot,
    DatasetVersion,
    FeatureDefinition,
    FeatureMaterialization,
    FeatureVersion,
)
from app.research_artifacts.fingerprints import stable_hash

DATASET_SCHEMA_VERSION = "market-bars-v1"


class DataQualityError(ValueError):
    pass


class DataLineageService:
    def __init__(self, session: Session, storage_root: Path | None = None) -> None:
        self.session = session
        self.storage_root = storage_root or get_settings().data_storage_root

    def create_dataset_version(
        self,
        *,
        name: str,
        bars: pl.DataFrame,
        provider: str,
        frequency: str,
        parent_version_id: UUID | None = None,
        transformation: str = "ingest",
        transformation_version: str = "v1",
        parameters: dict[str, Any] | None = None,
        adjustment_policy: str = "unadjusted",
    ) -> DatasetVersion:
        report = data_quality_report(bars, frequency)
        if not report["valid"]:
            raise DataQualityError(f"invalid dataset: {report['issues']}")
        payload = _fingerprint_rows(bars)
        checksum = stable_hash(payload)
        dataset = self.session.scalar(select(Dataset).where(Dataset.name == name))
        if dataset is None:
            dataset = Dataset(name=name)
            self.session.add(dataset)
            self.session.flush()
        existing = self.session.scalar(
            select(DatasetVersion).where(
                DatasetVersion.dataset_id == dataset.id, DatasetVersion.checksum == checksum
            )
        )
        if existing is not None:
            return existing
        version_number = (
            self.session.scalar(
                select(func.max(DatasetVersion.version)).where(
                    DatasetVersion.dataset_id == dataset.id
                )
            )
            or 0
        ) + 1
        storage_location = self._dataset_path(dataset.id, version_number)
        storage_location.parent.mkdir(parents=True, exist_ok=True)
        bars.sort("timestamp").write_parquet(storage_location)
        timestamps = bars.get_column("timestamp").to_list()
        version = DatasetVersion(
            dataset_id=dataset.id,
            version=version_number,
            symbols=sorted(set(str(value) for value in bars.get_column("symbol").to_list())),
            provider=provider,
            frequency=frequency,
            start_timestamp=_utc(timestamps[0]),
            end_timestamp=_utc(timestamps[-1]),
            schema_version=DATASET_SCHEMA_VERSION,
            row_count=bars.height,
            checksum=checksum,
            storage_location=str(storage_location),
            adjustment_policy=adjustment_policy,
            quality_report=report,
        )
        self.session.add(version)
        self.session.flush()
        self.session.add(
            DatasetLineage(
                child_dataset_version_id=version.id,
                parent_dataset_version_id=parent_version_id,
                transformation=transformation,
                transformation_version=transformation_version,
                parameters=parameters or {},
            )
        )
        self.session.flush()
        return version

    def bars_for_version(self, version_id: UUID) -> pl.DataFrame:
        version = self.require_version(version_id)
        path = Path(version.storage_location)
        if not path.is_file():
            raise DataQualityError(f"dataset storage is unavailable: {path}")
        return pl.read_parquet(path)

    def require_version(self, version_id: UUID) -> DatasetVersion:
        version = self.session.get(DatasetVersion, version_id)
        if version is None:
            raise DataQualityError("dataset version not found")
        return version

    def version_for_bars(
        self, *, name: str, bars: pl.DataFrame, provider: str, frequency: str
    ) -> DatasetVersion:
        return self.create_dataset_version(
            name=name, bars=bars, provider=provider, frequency=frequency
        )

    def create_snapshot(
        self, name: str, version_ids: list[UUID], feature_set: list[dict[str, Any]] | None = None
    ) -> DatasetSnapshot:
        versions = [self.require_version(version_id) for version_id in version_ids]
        if not versions:
            raise DataQualityError("a snapshot needs at least one dataset version")
        snapshot = DatasetSnapshot(
            name=name,
            dataset_version_ids=[str(version.id) for version in versions],
            universe=sorted({symbol for version in versions for symbol in version.symbols}),
            feature_set=feature_set or [],
            fingerprint=stable_hash(
                {
                    "versions": [version.checksum for version in versions],
                    "features": feature_set or [],
                }
            ),
        )
        self.session.add(snapshot)
        self.session.flush()
        return snapshot

    def lineage(self, dataset_id: UUID) -> list[DatasetLineage]:
        return list(
            self.session.scalars(
                select(DatasetLineage)
                .join(DatasetVersion, DatasetLineage.child_dataset_version_id == DatasetVersion.id)
                .where(DatasetVersion.dataset_id == dataset_id)
                .order_by(DatasetLineage.created_at)
            ).all()
        )

    def _dataset_path(self, dataset_id: UUID, version: int) -> Path:
        return self.storage_root / "datasets" / str(dataset_id) / f"v{version}.parquet"


class FeatureStore:
    """Small deterministic Parquet cache keyed by immutable data and feature versions."""

    def __init__(self, session: Session, storage_root: Path | None = None) -> None:
        self.session = session
        self.storage_root = storage_root or get_settings().data_storage_root

    def register(
        self,
        *,
        name: str,
        version: str,
        implementation: str,
        lookback: int,
        parameters: dict[str, Any] | None = None,
    ) -> FeatureVersion:
        definition = self.session.scalar(
            select(FeatureDefinition).where(FeatureDefinition.name == name)
        )
        if definition is None:
            definition = FeatureDefinition(name=name)
            self.session.add(definition)
            self.session.flush()
        existing = self.session.scalar(
            select(FeatureVersion).where(
                FeatureVersion.feature_definition_id == definition.id,
                FeatureVersion.version == version,
            )
        )
        if existing is not None:
            return existing
        feature = FeatureVersion(
            feature_definition_id=definition.id,
            version=version,
            input_schema={"required_columns": ["timestamp", "close"]},
            parameters=parameters or {},
            implementation=implementation,
            lookback=lookback,
            code_metadata={"engine": "polars", "point_in_time": True},
        )
        self.session.add(feature)
        self.session.flush()
        return feature

    def compute(
        self,
        dataset_version_id: UUID,
        feature_version_id: UUID,
        parameters: dict[str, Any] | None = None,
    ) -> pl.DataFrame:
        params = parameters or {}
        key = stable_hash(params)
        cached = self.session.scalar(
            select(FeatureMaterialization).where(
                FeatureMaterialization.dataset_version_id == dataset_version_id,
                FeatureMaterialization.feature_version_id == feature_version_id,
                FeatureMaterialization.parameters_hash == key,
            )
        )
        if cached is not None and Path(cached.storage_location).is_file():
            return pl.read_parquet(cached.storage_location)
        data = DataLineageService(self.session, self.storage_root).bars_for_version(
            dataset_version_id
        )
        feature = self.session.get(FeatureVersion, feature_version_id)
        if feature is None:
            raise DataQualityError("feature version not found")
        result = _compute_feature(data, feature, params)
        path = (
            self.storage_root
            / "features"
            / str(dataset_version_id)
            / str(feature_version_id)
            / f"{key}.parquet"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        result.write_parquet(path)
        materialization = FeatureMaterialization(
            dataset_version_id=dataset_version_id,
            feature_version_id=feature_version_id,
            parameters_hash=key,
            row_count=result.height,
            storage_location=str(path),
            checksum=stable_hash(_fingerprint_rows(result)),
        )
        self.session.add(materialization)
        self.session.flush()
        return result


def data_quality_report(bars: pl.DataFrame, frequency: str) -> dict[str, Any]:
    required = {"symbol", "timestamp", "open", "high", "low", "close", "volume"}
    missing_columns = sorted(required - set(bars.columns))
    issues: list[dict[str, Any]] = []
    if missing_columns:
        issues.append(
            {"rule": "required_columns", "count": len(missing_columns), "detail": missing_columns}
        )
        return {"valid": False, "row_count": bars.height, "issues": issues, "frequency": frequency}
    duplicates = bars.select(pl.struct(["symbol", "timestamp"]).is_duplicated().sum()).item()
    if duplicates:
        issues.append({"rule": "duplicate_timestamps", "count": int(duplicates)})
    nulls = sum(int(value) for value in bars.null_count().row(0))
    if nulls:
        issues.append({"rule": "nulls", "count": nulls})
    invalid_ohlc = bars.filter(
        (pl.col("open") <= 0)
        | (pl.col("high") < pl.max_horizontal("open", "close", "low"))
        | (pl.col("low") > pl.min_horizontal("open", "close", "high"))
        | (pl.col("close") <= 0)
    ).height
    if invalid_ohlc:
        issues.append({"rule": "invalid_ohlc", "count": invalid_ohlc})
    negative_volume = bars.filter(pl.col("volume") < 0).height
    if negative_volume:
        issues.append({"rule": "negative_volume", "count": negative_volume})
    timestamps = bars.get_column("timestamp").to_list()
    if any(_utc(value) != value for value in timestamps if isinstance(value, datetime)):
        issues.append(
            {"rule": "timezone_consistency", "count": 1, "detail": "timestamps must be UTC"}
        )
    ordered = bars.get_column("timestamp").to_list() == sorted(
        bars.get_column("timestamp").to_list()
    )
    if not ordered:
        issues.append({"rule": "ordering", "count": 1})
    gaps = _gaps(timestamps, frequency)
    if gaps:
        issues.append({"rule": "unexpected_gaps", "count": len(gaps), "examples": gaps[:5]})
    return {"valid": not issues, "row_count": bars.height, "issues": issues, "frequency": frequency}


def _compute_feature(
    data: pl.DataFrame, feature: FeatureVersion, parameters: dict[str, Any]
) -> pl.DataFrame:
    window = int(parameters.get("window", feature.parameters.get("window", feature.lookback)))
    if window < 1:
        raise DataQualityError("feature window must be positive")
    if feature.implementation == "rolling_mean_close":
        return data.select(
            "timestamp",
            "symbol",
            pl.col("close").rolling_mean(window_size=window).alias(feature_name(feature)),
        )
    if feature.implementation == "returns":
        return data.select(
            "timestamp",
            "symbol",
            (pl.col("close") / pl.col("close").shift(window) - 1).alias(feature_name(feature)),
        )
    raise DataQualityError(f"unsupported feature implementation: {feature.implementation}")


def feature_name(feature: FeatureVersion) -> str:
    return f"feature_{feature.id}"


def _gaps(timestamps: list[Any], frequency: str) -> list[str]:
    if frequency not in {"1m", "1h"} or len(timestamps) < 2:
        return []
    expected = 60 if frequency == "1m" else 3600
    return [
        f"{previous}->{current}"
        for previous, current in zip(timestamps, timestamps[1:], strict=False)
        if (_utc(current) - _utc(previous)).total_seconds() > expected * 1.5
    ]


def _fingerprint_rows(frame: pl.DataFrame) -> list[dict[str, Any]]:
    return frame.sort("timestamp").to_dicts()


def _utc(value: Any) -> datetime:
    if not isinstance(value, datetime):
        raise DataQualityError("timestamps must be datetime values")
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
