from typing import Any

from app.evolution.specification import StrategySpecification, complexity_score


def fitness_score(
    metrics: dict[str, Any],
    evaluation: dict[str, Any],
    regime_robustness: dict[str, Any],
    specification: StrategySpecification,
    risk_flags: list[str],
) -> dict[str, object]:
    sharpe = float(metrics.get("sharpe_ratio", 0.0))
    sortino = float(metrics.get("sortino_ratio", 0.0))
    drawdown = abs(float(metrics.get("max_drawdown", 0.0)))
    turnover = float(metrics.get("turnover", 0.0))
    trades = float(metrics.get("number_of_trades", 0.0))
    robustness = float(regime_robustness.get("score", 0.0)) / 100.0
    walk_forward = evaluation.get("walk_forward", {})
    consistency = (
        float(walk_forward.get("consistency", 0.0)) if isinstance(walk_forward, dict) else 0.0
    )
    complexity, complexity_components = complexity_score(specification)
    complexity_component = _clamp(1.0 - complexity / 20.0)
    flag_component = _clamp(1.0 - len(risk_flags) * 0.12)
    components = {
        "out_of_sample_sharpe": _clamp((sharpe + 2.0) / 4.0),
        "sortino": _clamp((sortino + 2.0) / 4.0),
        "drawdown_control": _clamp(1.0 - drawdown),
        "walk_forward_consistency": _clamp(consistency),
        "regime_robustness": _clamp(robustness),
        "turnover_control": _clamp(1.0 - turnover / 10.0),
        "trade_count": _clamp(trades / 10.0),
        "complexity": complexity_component,
        "overfitting_control": flag_component,
    }
    score = round(
        100.0
        * (
            components["out_of_sample_sharpe"] * 0.18
            + components["sortino"] * 0.1
            + components["drawdown_control"] * 0.14
            + components["walk_forward_consistency"] * 0.12
            + components["regime_robustness"] * 0.18
            + components["turnover_control"] * 0.08
            + components["trade_count"] * 0.08
            + components["complexity"] * 0.06
            + components["overfitting_control"] * 0.06
        ),
        4,
    )
    penalty_flags = list(risk_flags)
    penalty_flags.extend(str(flag) for flag in regime_robustness.get("flags", []))
    return {
        "score": score,
        "components": {key: round(value, 6) for key, value in components.items()},
        "complexity_score": complexity,
        "complexity_components": complexity_components,
        "penalty_flags": list(dict.fromkeys(penalty_flags)),
    }


def champion_decision(
    champion: dict[str, Any] | None,
    challenger: dict[str, Any],
) -> dict[str, Any]:
    if champion is None:
        return {"decision": "promote", "reason": "No existing champion."}
    champion_score = float(champion.get("score", 0.0))
    challenger_score = float(challenger.get("score", 0.0))
    challenger_flags = set(challenger.get("penalty_flags", []))
    blocking = {
        "REGIME_DEPENDENCE_HIGH",
        "HIGH_VOL_FAILURE",
        "SIDEWAYS_FAILURE",
        "OVERFITTING_HIGH",
    }
    if challenger_flags & blocking:
        return {"decision": "reject", "reason": "Blocking risk flags present."}
    if challenger_score >= champion_score + 2.0:
        return {"decision": "promote", "reason": "Challenger materially improves fitness."}
    return {"decision": "reject", "reason": "Challenger did not clear promotion margin."}


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
