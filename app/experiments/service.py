from datetime import datetime
from decimal import Decimal

import polars as pl
from sqlalchemy.orm import Session

from app.backtesting.backends import get_backtest_engine
from app.core.config import get_settings
from app.market_data.repository import MarketDataRepository
from app.models.experiment import BacktestTradeRecord, Experiment
from app.models.market_data import MarketBar
from app.regimes.engine import REGIME_VERSION, classify_regimes, summarize_transitions
from app.regimes.performance import performance_by_regime, regime_robustness_score
from app.research_artifacts.fingerprints import (
    BACKTESTER_VERSION,
    STRATEGY_VERSION,
    config_fingerprint,
    current_commit,
    environment_fingerprint,
    equity_charts,
    market_data_fingerprint,
)
from app.schemas.experiment import BacktestRequest


class ExperimentService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.market_data = MarketDataRepository(session)

    def run_backtest(self, request: BacktestRequest) -> Experiment:
        bars = self.market_data.list_bars(
            symbol=request.symbol,
            interval=request.interval,
            start=request.start,
            end=request.end,
        )
        if not bars:
            raise ValueError("no market bars found; ingest market data before running a backtest")

        frame = _bars_to_frame(bars)
        parameters = {
            "short_window": request.short_window,
            "long_window": request.long_window,
            "initial_capital": request.initial_capital,
            "slippage_bps": request.slippage_bps,
        }
        reproducibility_config = {
            "strategy_name": "moving_average_crossover",
            "symbol": request.symbol.upper(),
            "parameters": parameters,
            "start_date": request.start.isoformat(),
            "end_date": request.end.isoformat(),
            "data_interval": request.interval,
            "transaction_cost_bps": request.transaction_cost_bps,
            "slippage_bps": request.slippage_bps,
            "random_seed": None,
        }
        data_fingerprint = market_data_fingerprint(bars)
        engine = get_backtest_engine(get_settings().backtest_engine)
        result = engine.run_moving_average(
            frame,
            request.short_window,
            request.long_window,
            request.initial_capital,
            request.transaction_cost_bps,
            request.slippage_bps,
        )
        regime_observations = classify_regimes(bars)
        regime_performance = performance_by_regime(result.equity_curve, regime_observations)
        robustness_score, robustness_flags, robustness_components = regime_robustness_score(
            regime_performance
        )
        experiment = Experiment(
            strategy_name="moving_average_crossover",
            symbol=request.symbol.upper(),
            parameters=parameters,
            start_date=request.start,
            end_date=request.end,
            data_interval=request.interval,
            transaction_cost_bps=request.transaction_cost_bps,
            slippage_bps=request.slippage_bps,
            status="completed",
            metrics=result.metrics,
            run_metadata={
                **result.metadata,
                "charts": equity_charts(result.equity_curve),
                "reproducibility": {
                    "experiment_id": None,
                    "configuration": reproducibility_config,
                    "configuration_fingerprint": config_fingerprint(reproducibility_config),
                    "data_fingerprint": data_fingerprint,
                    "backtester_version": BACKTESTER_VERSION,
                    "strategy_version": STRATEGY_VERSION,
                    "workflow_version": None,
                    "agent_version": None,
                    "model_configuration": None,
                    "commit": current_commit(),
                    "environment": environment_fingerprint(),
                },
                "regime_version": REGIME_VERSION,
                "backtest_engine": {"name": engine.name, "version": engine.version},
                "regime_performance": regime_performance,
                "regime_robustness": {
                    "score": robustness_score,
                    "flags": robustness_flags,
                    "components": robustness_components,
                },
                "regime_transitions": summarize_transitions(regime_observations),
            },
            error_message=None,
        )
        self.session.add(experiment)
        self.session.flush()
        experiment.run_metadata = {
            **experiment.run_metadata,
            "reproducibility": {
                **experiment.run_metadata["reproducibility"],
                "experiment_id": str(experiment.id),
            },
        }
        self.session.add_all(
            [
                BacktestTradeRecord(
                    experiment_id=experiment.id,
                    timestamp=_coerce_timestamp(trade.timestamp),
                    side=trade.side,
                    quantity=Decimal(str(trade.quantity)),
                    price=Decimal(str(trade.price)),
                    notional=Decimal(str(trade.notional)),
                    transaction_cost=Decimal(str(trade.transaction_cost)),
                    slippage_cost=Decimal(str(trade.slippage_cost)),
                    realized_pnl=(
                        Decimal(str(trade.realized_pnl)) if trade.realized_pnl is not None else None
                    ),
                )
                for trade in result.trades
            ]
        )
        self.session.flush()
        self.session.refresh(experiment)
        return experiment


def _coerce_timestamp(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


def _bars_to_frame(bars: list[MarketBar]) -> pl.DataFrame:
    return pl.DataFrame(
        [
            {
                "timestamp": bar.timestamp,
                "open": float(bar.open),
                "high": float(bar.high),
                "low": float(bar.low),
                "close": float(bar.close),
                "volume": bar.volume,
            }
            for bar in bars
        ]
    ).sort("timestamp")
