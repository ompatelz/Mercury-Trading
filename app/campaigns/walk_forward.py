from datetime import date
from typing import Any

from app.campaigns.splits import Period


def build_walk_forward_windows(
    start_date: date, end_date: date, windows: int = 3
) -> list[dict[str, str]]:
    total_days = (end_date - start_date).days
    if total_days < windows + 3:
        return []
    step = max(1, total_days // (windows + 2))
    result: list[dict[str, str]] = []
    for index in range(windows):
        train_start = date.fromordinal(start_date.toordinal() + index * step)
        train_end = date.fromordinal(train_start.toordinal() + step * 2)
        test_end = date.fromordinal(min(train_end.toordinal() + step, end_date.toordinal()))
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


def aggregate_walk_forward(metrics_by_window: list[dict[str, Any]]) -> dict[str, float]:
    if not metrics_by_window:
        return {
            "window_count": 0.0,
            "average_sharpe": 0.0,
            "worst_drawdown": 0.0,
            "consistency": 0.0,
            "train_test_degradation": 0.0,
        }
    sharpes = [float(metrics.get("sharpe_ratio", 0.0)) for metrics in metrics_by_window]
    drawdowns = [abs(float(metrics.get("max_drawdown", 0.0))) for metrics in metrics_by_window]
    positive = sum(1 for value in sharpes if value > 0)
    return {
        "window_count": float(len(metrics_by_window)),
        "average_sharpe": round(sum(sharpes) / len(sharpes), 6),
        "worst_drawdown": round(max(drawdowns), 6),
        "consistency": round(positive / len(sharpes), 6),
        "train_test_degradation": 0.0,
    }


def period_from_dict(raw: dict[str, str]) -> Period:
    return Period(start=date.fromisoformat(raw["start"]), end=date.fromisoformat(raw["end"]))
