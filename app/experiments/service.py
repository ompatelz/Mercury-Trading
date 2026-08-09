from datetime import datetime
from decimal import Decimal

import polars as pl
from sqlalchemy.orm import Session

from app.backtesting.engine import run_moving_average_backtest
from app.market_data.repository import MarketDataRepository
from app.models.experiment import BacktestTradeRecord, Experiment
from app.models.market_data import MarketBar
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
        result = run_moving_average_backtest(
            bars=frame,
            short_window=request.short_window,
            long_window=request.long_window,
            initial_capital=request.initial_capital,
            transaction_cost_bps=request.transaction_cost_bps,
            slippage_bps=request.slippage_bps,
        )
        experiment = Experiment(
            strategy_name="moving_average_crossover",
            symbol=request.symbol.upper(),
            parameters={
                "short_window": request.short_window,
                "long_window": request.long_window,
                "initial_capital": request.initial_capital,
                "slippage_bps": request.slippage_bps,
            },
            start_date=request.start,
            end_date=request.end,
            data_interval=request.interval,
            transaction_cost_bps=request.transaction_cost_bps,
            slippage_bps=request.slippage_bps,
            status="completed",
            metrics=result.metrics,
            run_metadata=result.metadata,
            error_message=None,
        )
        self.session.add(experiment)
        self.session.flush()
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
