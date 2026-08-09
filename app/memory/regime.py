from statistics import mean, pstdev

from app.models.market_data import MarketBar


def classify_asset(symbol: str) -> str:
    upper = symbol.upper()
    if upper in {"BTC", "ETH", "SOL"} or upper.endswith("-USD"):
        return "crypto"
    return "equity"


def classify_market_regime(bars: list[MarketBar]) -> str:
    if len(bars) < 3:
        return "unknown_regime"

    closes = [float(bar.close) for bar in sorted(bars, key=lambda bar: bar.timestamp)]
    returns = [(closes[index] / closes[index - 1]) - 1.0 for index in range(1, len(closes))]
    total_return = (closes[-1] / closes[0]) - 1.0
    volatility = pstdev(returns) if len(returns) > 1 else 0.0
    abs_moves = [abs(value) for value in returns]
    directional_consistency = abs(mean(returns)) / mean(abs_moves) if mean(abs_moves) else 0.0

    direction = "sideways"
    if total_return > 0.03:
        direction = "bullish"
    elif total_return < -0.03:
        direction = "bearish"

    vol_bucket = "high_volatility" if volatility > 0.02 else "low_volatility"
    behavior = "trending" if directional_consistency >= 0.45 else "mean_reverting"
    return f"{direction}_{vol_bucket}_{behavior}"
