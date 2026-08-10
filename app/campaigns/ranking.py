from app.models.campaign import CampaignExperiment


def score_experiment(experiment: CampaignExperiment) -> tuple[float, dict[str, float], str]:
    metrics = experiment.metrics
    sharpe = float(metrics.get("sharpe_ratio", 0.0))
    sortino = float(metrics.get("sortino_ratio", 0.0))
    drawdown = abs(float(metrics.get("max_drawdown", 0.0)))
    turnover = float(metrics.get("turnover", 0.0))
    trades = float(metrics.get("number_of_trades", 0.0))
    flag_penalty = min(0.5, len(experiment.risk_flags) * 0.12)
    components = {
        "risk_adjusted_return": _clamp((sharpe + 2.0) / 4.0),
        "downside_quality": _clamp((sortino + 2.0) / 4.0),
        "drawdown_control": _clamp(1.0 - drawdown),
        "turnover_control": _clamp(1.0 - turnover / 10.0),
        "trade_count": _clamp(trades / 10.0),
        "overfitting_risk": _clamp(1.0 - flag_penalty),
    }
    score = round(
        100.0
        * (
            components["risk_adjusted_return"] * 0.25
            + components["downside_quality"] * 0.15
            + components["drawdown_control"] * 0.2
            + components["turnover_control"] * 0.1
            + components["trade_count"] * 0.1
            + components["overfitting_risk"] * 0.2
        ),
        4,
    )
    reason = (
        "Ranked by validation risk-adjusted return, drawdown control, turnover, "
        "trade count, and overfitting flags."
    )
    return score, components, reason


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 6)
