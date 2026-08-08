import polars as pl
from sqlalchemy.orm import Session

from app.backtesting.engine import run_moving_average_backtest
from app.market_data.repository import MarketDataRepository
from app.models.experiment import Experiment
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
        )
        experiment = Experiment(
            strategy_name="moving_average_crossover",
            symbol=request.symbol.upper(),
            parameters={
                "short_window": request.short_window,
                "long_window": request.long_window,
                "initial_capital": request.initial_capital,
            },
            start_date=request.start,
            end_date=request.end,
            data_interval=request.interval,
            transaction_cost_bps=request.transaction_cost_bps,
            status="completed",
            metrics=result.metrics,
            error_message=None,
        )
        self.session.add(experiment)
        self.session.flush()
        self.session.refresh(experiment)
        return experiment


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
