from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np


def relative_strength(base: Sequence[float], reference: Sequence[float]) -> list[float | None]:
    """Pointwise base/reference ratio; no narrative or signal direction is imposed."""
    if len(base) != len(reference):
        raise ValueError("relative-strength inputs must be aligned")
    return [
        None if divisor == 0 else value / divisor
        for value, divisor in zip(base, reference, strict=True)
    ]


def cross_sectional_rank(values: Mapping[str, float], *, descending: bool = True) -> dict[str, int]:
    """Stable tie-break by asset id makes selection deterministic."""
    ordered = sorted(
        values.items(), key=lambda item: ((-item[1]) if descending else item[1], item[0])
    )
    return {asset_id: rank for rank, (asset_id, _) in enumerate(ordered, start=1)}


def correlation(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        raise ValueError("correlation needs two equally sized aligned series")
    value = float(np.corrcoef(left, right)[0, 1])
    if not np.isfinite(value):
        raise ValueError("correlation is undefined for constant inputs")
    return value


def yield_curve_slope(short_rate: float, long_rate: float) -> float:
    return long_rate - short_rate
