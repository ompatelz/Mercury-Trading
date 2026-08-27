from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from app.alternative_data.schemas import AlignedValue, AlignmentPolicy, TimedObservation


def align_asof(
    *,
    targets: Iterable[datetime],
    observations: Iterable[TimedObservation],
    policy: AlignmentPolicy,
) -> list[AlignedValue]:
    """As-of join that can only select information released by each target timestamp.

    Missing, not-yet-released, and stale data remain observable outcomes rather than
    becoming silent fills.
    """
    releases = sorted(observations, key=lambda item: (item.available_at, item.observation_at))
    result: list[AlignedValue] = []
    for raw_target in targets:
        target = _utc(raw_target)
        candidates = [
            item
            for item in releases
            if item.available_at <= target
            and (
                not policy.require_observation_at_or_before_target or item.observation_at <= target
            )
        ]
        if not candidates:
            result.append(AlignedValue(target, _series(releases), None, None, None, "unavailable"))
            continue
        latest = max(candidates, key=lambda item: (item.observation_at, item.available_at))
        if not policy.forward_fill and latest.observation_at != target:
            result.append(AlignedValue(target, latest.series, None, None, None, "missing"))
            continue
        if policy.max_staleness and target - latest.observation_at > policy.max_staleness:
            result.append(
                AlignedValue(
                    target, latest.series, None, latest.observation_at, latest.available_at, "stale"
                )
            )
            continue
        result.append(
            AlignedValue(
                target,
                latest.series,
                latest.value,
                latest.observation_at,
                latest.available_at,
                "available",
            )
        )
    return result


def _series(releases: list[TimedObservation]) -> str:
    return releases[0].series if releases else "unknown"


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
