from sqlalchemy.orm import Session

from app.backtesting.registry import validate_strategy_spec
from app.experiments.service import ExperimentService
from app.research.schemas import (
    BacktestToolResult,
    ResearchExperimentRequest,
    StrategySpecification,
)
from app.schemas.experiment import BacktestRequest


def run_backtest_tool(
    request: ResearchExperimentRequest,
    strategy_spec: StrategySpecification,
    session: Session,
) -> BacktestToolResult:
    if strategy_spec.symbol.upper() != request.symbol.upper():
        raise ValueError("strategy symbol must match research request symbol")
    parameters = validate_strategy_spec(strategy_spec.strategy, strategy_spec.parameters)

    backtest_request = BacktestRequest(
        symbol=request.symbol,
        start=request.start_date,
        end=request.end_date,
        interval=request.interval,
        short_window=parameters["fast_window"],
        long_window=parameters["slow_window"],
        initial_capital=request.initial_capital,
        transaction_cost_bps=request.transaction_cost_bps,
        slippage_bps=request.slippage_bps,
    )
    experiment = ExperimentService(session).run_backtest(backtest_request)
    return BacktestToolResult(
        experiment_id=experiment.id,
        metrics=experiment.metrics,
        dataset={
            "symbol": experiment.symbol,
            "start_date": experiment.start_date.isoformat(),
            "end_date": experiment.end_date.isoformat(),
            "interval": experiment.data_interval,
            "candles_processed": experiment.run_metadata.get("candles_processed", 0),
        },
        strategy=experiment.strategy_name,
        parameters=parameters,
        execution_engine=request.execution_engine,
    )
