from dataclasses import dataclass
from datetime import datetime
from statistics import mean, pstdev

from app.models.market_data import MarketBar

REGIME_VERSION = "regime-v1"


@dataclass(frozen=True)
class RegimeObservation:
    timestamp: datetime
    symbol: str
    interval: str
    features: dict[str, float | int]
    trend_regime: str
    volatility_regime: str
    character_regime: str
    regime_version: str = REGIME_VERSION

    @property
    def composite_regime(self) -> str:
        return f"{self.trend_regime}_{self.volatility_regime}_{self.character_regime}"


def classify_regimes(
    bars: list[MarketBar],
    *,
    lookback: int = 20,
    regime_version: str = REGIME_VERSION,
) -> list[RegimeObservation]:
    ordered = sorted(bars, key=lambda item: item.timestamp)
    if not ordered:
        return []

    closes = [float(bar.close) for bar in ordered]
    highs = [float(bar.high) for bar in ordered]
    lows = [float(bar.low) for bar in ordered]
    observations: list[RegimeObservation] = []
    for index, bar in enumerate(ordered):
        start = max(0, index - lookback + 1)
        window_closes = closes[start : index + 1]
        window_highs = highs[start : index + 1]
        window_lows = lows[start : index + 1]
        returns = _returns(window_closes)
        slope = _normalized_slope(window_closes)
        realized_volatility = pstdev(returns) if len(returns) > 1 else 0.0
        drawdown = _drawdown(window_closes)
        autocorrelation = _autocorrelation(returns)
        atr_ratio = _atr_ratio(window_highs, window_lows, window_closes)
        trend_strength = abs(slope) / realized_volatility if realized_volatility else 0.0
        features: dict[str, float | int] = {
            "lookback": lookback,
            "observations": len(window_closes),
            "rolling_return": _rolling_return(window_closes),
            "ma_slope": slope,
            "realized_volatility": realized_volatility,
            "atr_ratio": atr_ratio,
            "drawdown": drawdown,
            "autocorrelation": autocorrelation,
            "trend_strength": trend_strength,
        }
        observations.append(
            RegimeObservation(
                timestamp=bar.timestamp,
                symbol=bar.symbol.upper(),
                interval=bar.interval,
                features={key: round(value, 8) for key, value in features.items()},
                trend_regime=_trend_regime(slope, features["rolling_return"], trend_strength),
                volatility_regime=_volatility_regime(realized_volatility, atr_ratio),
                character_regime=_character_regime(autocorrelation, trend_strength),
                regime_version=regime_version,
            )
        )
    return observations


def summarize_transitions(observations: list[RegimeObservation]) -> list[dict[str, object]]:
    if not observations:
        return []
    transitions: list[dict[str, object]] = []
    current = observations[0]
    start = current.timestamp
    duration = 1
    for observation in observations[1:]:
        if observation.composite_regime == current.composite_regime:
            duration += 1
            continue
        transitions.append(
            {
                "from_regime": current.composite_regime,
                "to_regime": observation.composite_regime,
                "start": start.isoformat(),
                "end": current.timestamp.isoformat(),
                "duration_bars": duration,
                "transition_at": observation.timestamp.isoformat(),
            }
        )
        current = observation
        start = observation.timestamp
        duration = 1
    transitions.append(
        {
            "from_regime": current.composite_regime,
            "to_regime": None,
            "start": start.isoformat(),
            "end": current.timestamp.isoformat(),
            "duration_bars": duration,
            "transition_at": None,
        }
    )
    return transitions


def _returns(values: list[float]) -> list[float]:
    return [(values[index] / values[index - 1]) - 1.0 for index in range(1, len(values))]


def _rolling_return(values: list[float]) -> float:
    if len(values) < 2 or values[0] == 0.0:
        return 0.0
    return values[-1] / values[0] - 1.0


def _normalized_slope(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    average_price = mean(values)
    if average_price == 0.0:
        return 0.0
    return ((values[-1] - values[0]) / (len(values) - 1)) / average_price


def _drawdown(values: list[float]) -> float:
    if not values:
        return 0.0
    running_high = max(values)
    if running_high == 0.0:
        return 0.0
    return values[-1] / running_high - 1.0


def _autocorrelation(values: list[float]) -> float:
    if len(values) < 3:
        return 0.0
    left = values[:-1]
    right = values[1:]
    left_mean = mean(left)
    right_mean = mean(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right, strict=True))
    left_denominator = sum((a - left_mean) ** 2 for a in left)
    right_denominator = sum((b - right_mean) ** 2 for b in right)
    denominator = (left_denominator * right_denominator) ** 0.5
    return numerator / denominator if denominator else 0.0


def _atr_ratio(highs: list[float], lows: list[float], closes: list[float]) -> float:
    if len(closes) < 2:
        return 0.0
    true_ranges = []
    for index in range(1, len(closes)):
        true_ranges.append(
            max(
                highs[index] - lows[index],
                abs(highs[index] - closes[index - 1]),
                abs(lows[index] - closes[index - 1]),
            )
        )
    average_close = mean(closes)
    return mean(true_ranges) / average_close if average_close else 0.0


def _trend_regime(slope: float, rolling_return: float | int, trend_strength: float | int) -> str:
    if slope > 0.0008 and rolling_return > 0.015 and trend_strength >= 0.25:
        return "bullish"
    if slope < -0.0008 and rolling_return < -0.015 and trend_strength >= 0.25:
        return "bearish"
    return "sideways"


def _volatility_regime(realized_volatility: float, atr_ratio: float) -> str:
    combined = max(realized_volatility, atr_ratio / 2.0)
    if combined < 0.008:
        return "low"
    if combined > 0.025:
        return "high"
    return "normal"


def _character_regime(autocorrelation: float | int, trend_strength: float | int) -> str:
    if autocorrelation < -0.15 and trend_strength < 0.55:
        return "mean_reverting"
    return "trending"
