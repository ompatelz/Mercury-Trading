from typing import Any


def detect_overfitting(
    train_metrics: dict[str, Any],
    validation_metrics: dict[str, Any],
    constraints: dict[str, Any],
) -> list[str]:
    flags: list[str] = []
    train_sharpe = float(train_metrics.get("sharpe_ratio", 0.0))
    validation_sharpe = float(validation_metrics.get("sharpe_ratio", 0.0))
    validation_drawdown = abs(float(validation_metrics.get("max_drawdown", 0.0)))
    turnover = float(validation_metrics.get("turnover", 0.0))
    trades = int(validation_metrics.get("number_of_trades", 0))

    if train_sharpe > 0 and validation_sharpe < train_sharpe * 0.5:
        flags.append("VALIDATION_DEGRADATION_HIGH")
    if validation_drawdown > float(constraints.get("max_drawdown", 0.35)):
        flags.append("DRAWDOWN_LIMIT_BREACHED")
    if turnover > float(constraints.get("max_turnover", 8.0)):
        flags.append("TURNOVER_TOO_HIGH")
    if trades < int(constraints.get("minimum_trade_count", 1)):
        flags.append("TRADE_COUNT_TOO_LOW")
    if validation_sharpe < float(constraints.get("minimum_validation_sharpe", -2.0)):
        flags.append("VALIDATION_PERFORMANCE_WEAK")
    return flags
