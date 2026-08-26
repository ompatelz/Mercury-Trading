"""Campaign adapter for the reusable portfolio engine."""

from dataclasses import dataclass
from typing import Any, cast

from app.models.campaign import CampaignExperiment, ResearchCampaign
from app.portfolio.engine import (
    PortfolioDefinition,
    PortfolioResult,
    StrategySeries,
    construct_portfolio,
)


@dataclass(frozen=True)
class CampaignPortfolioResult:
    weights: dict[str, float]
    metrics: dict[str, Any]
    definition: dict[str, Any]
    compatibility: dict[str, Any]
    rebalance_history: list[dict[str, Any]]
    incremental_benefit: dict[str, dict[str, float]]
    rejection_reasons: list[str]
    ranking: dict[str, Any]


def evaluate_portfolio(
    campaign: ResearchCampaign, experiments: list[CampaignExperiment], weighting_method: str
) -> CampaignPortfolioResult:
    strategies = [
        StrategySeries(
            strategy_id=str(item.id),
            version=str(item.experiment_id),
            family=item.strategy_family,
            symbol=item.symbol,
            returns=list(item.evaluation.get("validation_return_series", [])),
            regime_performance=dict(item.evaluation.get("validation_regime_performance", {})),
        )
        for item in experiments
    ]
    definition = PortfolioDefinition(
        strategy_ids=[item.strategy_id for item in strategies],
        strategy_versions={item.strategy_id: item.version for item in strategies},
        allocation_method=cast(Any, weighting_method),
        dynamic_method=cast(Any, campaign.constraints.get("portfolio_dynamic_method", "static")),
        rebalance_frequency=cast(
            Any, campaign.constraints.get("portfolio_rebalance_frequency", "monthly")
        ),
        lookback_periods=int(campaign.constraints.get("portfolio_lookback_periods", 20)),
        constraints=dict(campaign.constraints.get("portfolio_constraints", {})),
        universe=campaign.symbols,
        validation_period=campaign.split_definition["validation"],
        transaction_cost_bps=float(campaign.constraints.get("transaction_cost_bps", 1.0)),
    )
    result: PortfolioResult = construct_portfolio(definition, strategies)
    return CampaignPortfolioResult(
        weights=result.weights,
        metrics=result.metrics | {"return_series": result.return_series},
        definition=definition.as_dict(),
        compatibility=result.compatibility,
        rebalance_history=result.rebalance_history,
        incremental_benefit=result.incremental_benefit,
        rejection_reasons=result.rejection_reasons,
        ranking=_ranking(result),
    )


def _ranking(result: PortfolioResult) -> dict[str, Any]:
    metrics = result.metrics
    components = {
        "oos_sharpe": float(metrics.get("sharpe_ratio", 0.0)),
        "drawdown": -abs(float(metrics.get("max_drawdown", 0.0))),
        "diversification": float(metrics.get("diversification_ratio", 0.0)),
        "turnover": -float(metrics.get("turnover", 0.0)),
        "cost": -float(metrics.get("transaction_cost", 0.0)),
    }
    return {
        "score": round(sum(components.values()), 8),
        "components": components,
        "explanation": "OOS streams, diversification, costs, and turnover were scored.",
        "promotion_decision": "reject" if result.rejection_reasons else "challenger",
    }
