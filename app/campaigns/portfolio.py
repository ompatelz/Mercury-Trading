import math
from typing import Any

from app.models.campaign import CampaignExperiment


def evaluate_portfolio(
    experiments: list[CampaignExperiment], weighting_method: str
) -> tuple[dict[str, float], dict[str, float], float, dict[str, Any]]:
    if not experiments:
        raise ValueError("portfolio evaluation requires at least one strategy")
    ids = [str(experiment.id) for experiment in experiments]
    weights = _weights(experiments, weighting_method)
    returns = [float(experiment.metrics.get("total_return", 0.0)) for experiment in experiments]
    volatility = [
        max(float(experiment.metrics.get("volatility", 0.0)), 0.0001) for experiment in experiments
    ]
    portfolio_return = sum(weights[ids[index]] * returns[index] for index in range(len(ids)))
    portfolio_vol = math.sqrt(
        sum((weights[ids[index]] * volatility[index]) ** 2 for index in range(len(ids)))
    )
    metrics = {
        "portfolio_return": round(portfolio_return, 6),
        "portfolio_volatility": round(portfolio_vol, 6),
        "portfolio_sharpe": round(portfolio_return / portfolio_vol, 6) if portfolio_vol else 0.0,
        "strategy_count": float(len(experiments)),
    }
    average_vol = sum(volatility) / len(volatility)
    diversification_benefit = round(max(0.0, average_vol - portfolio_vol), 6)
    return weights, metrics, diversification_benefit, _correlation_matrix(experiments)


def _weights(experiments: list[CampaignExperiment], method: str) -> dict[str, float]:
    ids = [str(experiment.id) for experiment in experiments]
    if method == "equal_weight":
        weight = round(1.0 / len(ids), 6)
        return {strategy_id: weight for strategy_id in ids}
    inverse_vol = [
        1.0 / max(float(experiment.metrics.get("volatility", 0.0)), 0.0001)
        for experiment in experiments
    ]
    total = sum(inverse_vol)
    if method in {"volatility_adjusted", "risk_parity"}:
        return {ids[index]: round(inverse_vol[index] / total, 6) for index in range(len(ids))}
    raise ValueError("weighting method must be equal_weight, volatility_adjusted, or risk_parity")


def _correlation_matrix(experiments: list[CampaignExperiment]) -> dict[str, Any]:
    ids = [str(experiment.id) for experiment in experiments]
    matrix: dict[str, Any] = {}
    for left in experiments:
        row: list[float] = []
        for right in experiments:
            same_family = left.strategy_family == right.strategy_family
            same_symbol = left.symbol == right.symbol
            if left.id == right.id:
                correlation = 1.0
            elif same_family and same_symbol:
                correlation = 0.75
            else:
                correlation = 0.35
            row.append(correlation)
        matrix[str(left.id)] = row
    matrix["columns"] = ids
    return matrix
