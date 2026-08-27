from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.alternative_data.schemas import Asset, UniverseDefinition
from app.models.alternative_data import ResearchAsset, ResearchUniverse, ResearchUniverseMembership
from app.models.data import DatasetVersion


class DataAvailabilityError(ValueError):
    pass


class AlternativeDataService:
    """Small catalog boundary used by campaigns and agents to reject invented inputs."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def register_asset(self, asset: Asset) -> ResearchAsset:
        existing = self.session.scalar(
            select(ResearchAsset).where(ResearchAsset.stable_identifier == asset.asset_id)
        )
        if existing is not None:
            return existing
        record = ResearchAsset(
            stable_identifier=asset.asset_id,
            symbol=asset.symbol.upper(),
            asset_class=asset.asset_class.value,
            exchange=asset.exchange,
            currency=asset.currency.upper(),
            timezone=asset.timezone,
            provider_identifiers=asset.provider_identifiers,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def register_universe(self, universe: UniverseDefinition) -> ResearchUniverse:
        existing = self.session.scalar(
            select(ResearchUniverse).where(
                ResearchUniverse.name == universe.name, ResearchUniverse.version == universe.version
            )
        )
        if existing is not None:
            return existing
        record = ResearchUniverse(
            name=universe.name,
            version=universe.version,
            filters=universe.filters,
            effective_from=_utc(universe.effective_from),
            effective_to=_utc(universe.effective_to) if universe.effective_to else None,
            survivorship_bias_risk=universe.survivorship_bias_risk,
            limitations=(["SURVIVORSHIP_BIAS_RISK"] if universe.survivorship_bias_risk else []),
        )
        self.session.add(record)
        self.session.flush()
        for stable_identifier in sorted(universe.membership):
            asset = self.session.scalar(
                select(ResearchAsset).where(ResearchAsset.stable_identifier == stable_identifier)
            )
            if asset is None:
                raise DataAvailabilityError(
                    f"universe member is not a registered asset: {stable_identifier}"
                )
            self.session.add(
                ResearchUniverseMembership(
                    universe_id=record.id,
                    asset_id=asset.id,
                    effective_from=_utc(universe.effective_from),
                    effective_to=_utc(universe.effective_to) if universe.effective_to else None,
                )
            )
        self.session.flush()
        return record

    def catalog(self) -> dict[str, object]:
        versions = list(
            self.session.scalars(select(DatasetVersion).order_by(DatasetVersion.ingested_at))
        )
        assets = list(self.session.scalars(select(ResearchAsset).order_by(ResearchAsset.symbol)))
        universes = list(
            self.session.scalars(select(ResearchUniverse).order_by(ResearchUniverse.name))
        )
        return {
            "datasets": [
                {
                    "id": str(item.id),
                    "provider": item.provider,
                    "frequency": item.frequency,
                    "coverage": [item.start_timestamp.isoformat(), item.end_timestamp.isoformat()],
                    "quality": item.quality_report,
                    "asset_classes": _asset_classes(item.symbols, assets),
                }
                for item in versions
            ],
            "assets": [
                {
                    "id": item.stable_identifier,
                    "symbol": item.symbol,
                    "asset_class": item.asset_class,
                    "currency": item.currency,
                    "timezone": item.timezone,
                }
                for item in assets
            ],
            "universes": [
                {
                    "name": item.name,
                    "version": item.version,
                    "effective_from": item.effective_from.isoformat(),
                    "effective_to": item.effective_to.isoformat() if item.effective_to else None,
                    "limitations": item.limitations,
                }
                for item in universes
            ],
        }

    def require_available_inputs(self, requirements: list[str]) -> None:
        available = {item.provider.lower() for item in self.session.scalars(select(DatasetVersion))}
        missing = sorted({item.lower() for item in requirements} - available)
        if missing:
            raise DataAvailabilityError(f"unavailable research inputs: {missing}")


def _asset_classes(symbols: list[str], assets: list[ResearchAsset]) -> list[str]:
    by_symbol = {item.symbol: item.asset_class for item in assets}
    return sorted({by_symbol[symbol] for symbol in symbols if symbol in by_symbol})


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
