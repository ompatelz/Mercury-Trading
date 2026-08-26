import hashlib
import json
import platform
import subprocess
import sys
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import polars as pl

from app.models.market_data import MarketBar

BACKTESTER_VERSION = "moving-average-backtester-v2"
STRATEGY_VERSION = "moving-average-crossover-v1"


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(_json_safe(payload), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def market_data_fingerprint(bars: list[MarketBar]) -> dict[str, Any]:
    rows = [
        {
            "timestamp": bar.timestamp.isoformat(),
            "open": str(bar.open),
            "high": str(bar.high),
            "low": str(bar.low),
            "close": str(bar.close),
            "volume": int(bar.volume),
        }
        for bar in sorted(bars, key=lambda item: item.timestamp)
    ]
    return {
        "row_count": len(rows),
        "first_timestamp": rows[0]["timestamp"] if rows else None,
        "last_timestamp": rows[-1]["timestamp"] if rows else None,
        "sha256": stable_hash(rows),
    }


def config_fingerprint(config: dict[str, Any]) -> str:
    return stable_hash(config)


def environment_fingerprint() -> dict[str, Any]:
    payload = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "implementation": platform.python_implementation(),
    }
    return {**payload, "sha256": stable_hash(payload)}


def current_commit() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception:
        return None
    value = completed.stdout.strip()
    return value or None


def equity_charts(frame: pl.DataFrame) -> dict[str, Any]:
    if frame.is_empty():
        return {"equity_curve": [], "drawdown": [], "return_distribution": []}
    rows = frame.select(["timestamp", "equity", "strategy_return"]).to_dicts()
    equity_values = [float(row["equity"]) for row in rows]
    running_max = 0.0
    equity_curve = []
    drawdown = []
    returns = []
    for row, equity in zip(rows, equity_values, strict=True):
        timestamp = _timestamp_label(row["timestamp"])
        running_max = max(running_max, equity)
        drawdown_value = equity / running_max - 1.0 if running_max else 0.0
        strategy_return = float(row["strategy_return"])
        equity_curve.append({"timestamp": timestamp, "equity": equity})
        drawdown.append({"timestamp": timestamp, "drawdown": drawdown_value})
        returns.append(strategy_return)
    return {
        "equity_curve": equity_curve,
        "drawdown": drawdown,
        "return_distribution": _return_distribution(returns),
    }


def _return_distribution(returns: list[float]) -> list[dict[str, Any]]:
    if not returns:
        return []
    buckets = {
        "< -2%": 0,
        "-2% to -1%": 0,
        "-1% to 0%": 0,
        "0% to 1%": 0,
        "1% to 2%": 0,
        "> 2%": 0,
    }
    for value in returns:
        if value < -0.02:
            buckets["< -2%"] += 1
        elif value < -0.01:
            buckets["-2% to -1%"] += 1
        elif value < 0.0:
            buckets["-1% to 0%"] += 1
        elif value <= 0.01:
            buckets["0% to 1%"] += 1
        elif value <= 0.02:
            buckets["1% to 2%"] += 1
        else:
            buckets["> 2%"] += 1
    return [{"bucket": bucket, "count": count} for bucket, count in buckets.items()]


def _timestamp_label(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_safe(item) for item in value]
    return value
