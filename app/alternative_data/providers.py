from datetime import date
from typing import Protocol

from app.alternative_data.schemas import ProviderMetadata, TimedObservation


class DatasetProvider(Protocol):
    """Providers share provenance and availability semantics, not a forced value schema."""

    def metadata(self) -> ProviderMetadata: ...


class MacroProvider(DatasetProvider, Protocol):
    def fetch_observations(self, series: str, start: date, end: date) -> list[TimedObservation]: ...


class FundamentalProvider(DatasetProvider, Protocol):
    def fetch_observations(
        self, asset_id: str, start: date, end: date
    ) -> list[TimedObservation]: ...


class AlternativeDataProvider(DatasetProvider, Protocol):
    def fetch_observations(self, series: str, start: date, end: date) -> list[TimedObservation]: ...
