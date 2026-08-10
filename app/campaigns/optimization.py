import hashlib
import importlib
import itertools
import random
from typing import Any, Protocol

DEFAULT_PARAMETER_SPACE: dict[str, list[int]] = {
    "short_window": [2, 3, 5, 8],
    "long_window": [5, 8, 13, 21],
}


def generate_parameter_variants(
    parameter_space: dict[str, Any] | None,
    method: str,
    max_variants: int,
    seed: int = 17,
) -> list[dict[str, int | float]]:
    normalized = _normalize_space(parameter_space or DEFAULT_PARAMETER_SPACE)
    if method == "grid":
        variants = _grid_search(normalized)
    elif method == "random":
        variants = _random_search(normalized, max_variants=max_variants, seed=seed)
    elif method == "bayesian":
        variants = _optuna_search(normalized, max_variants=max_variants)
    else:
        raise ValueError("optimization method must be grid, random, or bayesian")
    valid = [variant for variant in variants if _valid_windows(variant)]
    return valid[:max_variants]


def idempotency_key(campaign_id: str, symbol: str, parameters: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        f"{campaign_id}:{symbol}:{sorted(parameters.items())}".encode()
    ).hexdigest()
    return digest[:32]


def _normalize_space(parameter_space: dict[str, Any]) -> dict[str, list[int | float]]:
    normalized: dict[str, list[int | float]] = {}
    for name, values in parameter_space.items():
        if isinstance(values, dict):
            start = values["min"]
            end = values["max"]
            step = values.get("step")
            if step is None:
                midpoint = (start + end) / 2
                normalized[name] = [start, midpoint, end]
            else:
                normalized[name] = list(range(int(start), int(end) + 1, int(step)))
        else:
            normalized[name] = list(values)
    return normalized


def _grid_search(space: dict[str, list[int | float]]) -> list[dict[str, int | float]]:
    keys = list(space)
    return [
        dict(zip(keys, values, strict=True))
        for values in itertools.product(*(space[key] for key in keys))
    ]


def _random_search(
    space: dict[str, list[int | float]], max_variants: int, seed: int
) -> list[dict[str, int | float]]:
    rng = random.Random(seed)
    variants = _grid_search(space)
    rng.shuffle(variants)
    return variants[:max_variants]


def _bayesian_like_search(
    space: dict[str, list[int | float]], max_variants: int
) -> list[dict[str, int | float]]:
    variants = _grid_search(space)
    center = {
        key: sum(float(value) for value in values) / len(values) for key, values in space.items()
    }
    return sorted(
        variants,
        key=lambda variant: sum(
            abs(float(value) - center[key]) / max(abs(center[key]), 1.0)
            for key, value in variant.items()
        ),
    )[:max_variants]


def _optuna_search(
    space: dict[str, list[int | float]], max_variants: int
) -> list[dict[str, int | float]]:
    try:
        optuna = importlib.import_module("optuna")
    except ModuleNotFoundError:
        return _bayesian_like_search(space, max_variants)

    sampler = optuna.samplers.TPESampler(seed=19)
    study = optuna.create_study(direction="maximize", sampler=sampler)
    center = {
        key: sum(float(value) for value in values) / len(values) for key, values in space.items()
    }

    def objective(trial: _Trial) -> float:
        parameters = {key: trial.suggest_categorical(key, values) for key, values in space.items()}
        trial.set_user_attr("parameters", parameters)
        if not _valid_windows(parameters):
            return -1_000.0
        distance = sum(
            abs(float(value) - center[key]) / max(abs(center[key]), 1.0)
            for key, value in parameters.items()
        )
        return -distance

    study.optimize(objective, n_trials=max_variants)
    return [
        dict(trial.user_attrs["parameters"])
        for trial in sorted(study.trials, key=lambda item: item.value or -1_000.0, reverse=True)
        if "parameters" in trial.user_attrs
    ][:max_variants]


class _Trial(Protocol):
    user_attrs: dict[str, Any]

    def suggest_categorical(self, name: str, choices: list[int | float]) -> int | float: ...

    def set_user_attr(self, key: str, value: Any) -> None: ...


def _valid_windows(parameters: dict[str, Any]) -> bool:
    short_window = int(parameters.get("short_window", 0))
    long_window = int(parameters.get("long_window", 0))
    return short_window >= 2 and long_window >= 3 and short_window < long_window
