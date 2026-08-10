from datetime import date
from typing import Any

from app.campaigns.splits import Period


def build_walk_forward_windows(
    start_date: date,
    end_date: date,
    windows: int = 3,
    min_train_days: int = 3,
    min_test_days: int = 3,
) -> list[dict[str, str]]:
    total_days = (end_date - start_date).days
    if total_days < min_train_days + min_test_days:
        return []
    step = max(min_test_days, total_days // (windows + 1))
    train_span = max(min_train_days, step)
    result: list[dict[str, str]] = []
    for index in range(windows):
        train_start = date.fromordinal(start_date.toordinal() + index * step)
        train_end = date.fromordinal(train_start.toordinal() + train_span)
        test_end = date.fromordinal(train_end.toordinal() + step)
        if train_start < train_end < test_end <= end_date:
            result.append(
                {
                    "train_start": train_start.isoformat(),
                    "train_end": train_end.isoformat(),
                    "test_start": train_end.isoformat(),
                    "test_end": test_end.isoformat(),
                }
            )
    return result


def aggregate_walk_forward(window_results: list[dict[str, Any]]) -> dict[str, float]:
    if not window_results:
        return {
            "window_count": 0.0,
            "average_out_of_sample_sharpe": 0.0,
            "worst_drawdown": 0.0,
            "return_consistency": 0.0,
            "train_test_degradation": 0.0,
            "parameter_stability": 1.0,
        }
    test_metrics = [dict(result.get("test_metrics", result)) for result in window_results]
    train_metrics = [dict(result.get("train_metrics", {})) for result in window_results]
    sharpes = [float(metrics.get("sharpe_ratio", 0.0)) for metrics in test_metrics]
    drawdowns = [abs(float(metrics.get("max_drawdown", 0.0))) for metrics in test_metrics]
    positive = sum(1 for value in sharpes if value > 0)
    degradation = [
        max(
            0.0,
            float(train.get("sharpe_ratio", 0.0)) - float(test.get("sharpe_ratio", 0.0)),
        )
        for train, test in zip(train_metrics, test_metrics, strict=True)
    ]
    return {
        "window_count": float(len(window_results)),
        "average_out_of_sample_sharpe": round(sum(sharpes) / len(sharpes), 6),
        "worst_drawdown": round(max(drawdowns), 6),
        "return_consistency": round(positive / len(sharpes), 6),
        "train_test_degradation": round(sum(degradation) / len(degradation), 6),
        "parameter_stability": 1.0,
    }


def period_from_dict(raw: dict[str, str]) -> Period:
    return Period(start=date.fromisoformat(raw["start"]), end=date.fromisoformat(raw["end"]))
