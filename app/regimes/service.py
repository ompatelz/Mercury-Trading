from datetime import date
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.experiments.repository import ExperimentRepository
from app.market_data.repository import MarketDataRepository
from app.models.regime import MarketRegimeLabel
from app.regimes.engine import (
    REGIME_VERSION,
    RegimeObservation,
    classify_regimes,
    summarize_transitions,
)


class RegimeService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.market_data = MarketDataRepository(session)

    def compute_and_persist(
        self,
        symbol: str,
        *,
        interval: str = "1d",
        start: date | None = None,
        end: date | None = None,
        lookback: int = 20,
        regime_version: str = REGIME_VERSION,
        replace: bool = True,
    ) -> list[MarketRegimeLabel]:
        bars = self.market_data.list_bars(
            symbol=symbol,
            interval=interval,
            start=start,
            end=end,
        )
        observations = classify_regimes(bars, lookback=lookback, regime_version=regime_version)
        if replace and observations:
            self.session.execute(
                delete(MarketRegimeLabel).where(
                    MarketRegimeLabel.symbol == symbol.upper(),
                    MarketRegimeLabel.interval == interval,
                    MarketRegimeLabel.regime_version == regime_version,
                    MarketRegimeLabel.timestamp.in_(
                        [observation.timestamp for observation in observations]
                    ),
                )
            )
        labels = [_label_from_observation(observation) for observation in observations]
        self.session.add_all(labels)
        self.session.flush()
        return labels

    def list_labels(
        self,
        symbol: str | None = None,
        *,
        interval: str = "1d",
        regime_version: str = REGIME_VERSION,
    ) -> list[MarketRegimeLabel]:
        statement = select(MarketRegimeLabel).where(
            MarketRegimeLabel.interval == interval,
            MarketRegimeLabel.regime_version == regime_version,
        )
        if symbol is not None:
            statement = statement.where(MarketRegimeLabel.symbol == symbol.upper())
        return list(self.session.scalars(statement.order_by(MarketRegimeLabel.timestamp)))

    def transitions(
        self,
        symbol: str,
        *,
        interval: str = "1d",
        regime_version: str = REGIME_VERSION,
    ) -> list[dict[str, object]]:
        labels = self.list_labels(symbol, interval=interval, regime_version=regime_version)
        observations = [
            RegimeObservation(
                timestamp=label.timestamp,
                symbol=label.symbol,
                interval=label.interval,
                features=label.features,
                trend_regime=label.trend_regime,
                volatility_regime=label.volatility_regime,
                character_regime=label.character_regime,
                regime_version=label.regime_version,
            )
            for label in labels
        ]
        return summarize_transitions(observations)

    def experiment_regime_performance(self, experiment_id: UUID) -> dict[str, object]:
        experiment = ExperimentRepository(self.session).get(experiment_id)
        if experiment is None:
            raise ValueError("experiment not found")
        return {
            "experiment_id": str(experiment.id),
            "regime_performance": experiment.run_metadata.get("regime_performance", {}),
            "regime_robustness": experiment.run_metadata.get("regime_robustness", {}),
            "regime_version": experiment.run_metadata.get("regime_version", REGIME_VERSION),
        }


def _label_from_observation(observation: RegimeObservation) -> MarketRegimeLabel:
    return MarketRegimeLabel(
        symbol=observation.symbol,
        interval=observation.interval,
        timestamp=observation.timestamp,
        features=observation.features,
        trend_regime=observation.trend_regime,
        volatility_regime=observation.volatility_regime,
        character_regime=observation.character_regime,
        composite_regime=observation.composite_regime,
        regime_version=observation.regime_version,
    )
