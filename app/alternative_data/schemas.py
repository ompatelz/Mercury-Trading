from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any


class AssetClass(StrEnum):
    EQUITY = "equity"
    ETF = "etf"
    INDEX = "index"
    FX = "fx"
    CRYPTO = "crypto"
    FUTURE = "future"


class DatasetKind(StrEnum):
    MARKET_PRICE = "market_price"
    MACRO = "macro"
    FUNDAMENTAL = "fundamental"
    ALTERNATIVE = "alternative"


@dataclass(frozen=True)
class Asset:
    """A stable research identity; a display ticker is never treated as permanent."""

    asset_id: str
    symbol: str
    asset_class: AssetClass
    currency: str
    timezone: str
    exchange: str | None = None
    provider_identifiers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderMetadata:
    provider: str
    provider_version: str
    dataset_kind: DatasetKind
    frequency: str
    coverage_start: datetime
    coverage_end: datetime
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class TimedObservation:
    """One release with both what it describes and when it became knowable."""

    series: str
    observation_at: datetime
    available_at: datetime
    value: float
    asset_id: str | None = None
    source_release_id: str | None = None

    def __post_init__(self) -> None:
        observation_at = _utc(self.observation_at)
        available_at = _utc(self.available_at)
        if available_at < observation_at:
            raise ValueError("available_at cannot precede observation_at")
        object.__setattr__(self, "observation_at", observation_at)
        object.__setattr__(self, "available_at", available_at)


@dataclass(frozen=True)
class AlignmentPolicy:
    """All frequency bridging is explicit and included in feature/cache provenance."""

    forward_fill: bool = True
    max_staleness: timedelta | None = None
    require_observation_at_or_before_target: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "forward_fill": self.forward_fill,
            "max_staleness_seconds": (
                int(self.max_staleness.total_seconds()) if self.max_staleness else None
            ),
            "require_observation_at_or_before_target": self.require_observation_at_or_before_target,
        }


@dataclass(frozen=True)
class AlignedValue:
    target_at: datetime
    series: str
    value: float | None
    observation_at: datetime | None
    available_at: datetime | None
    status: str


@dataclass(frozen=True)
class UniverseDefinition:
    name: str
    version: str
    membership: tuple[str, ...]
    effective_from: datetime
    effective_to: datetime | None = None
    filters: dict[str, Any] = field(default_factory=dict)
    survivorship_bias_risk: bool = False


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
