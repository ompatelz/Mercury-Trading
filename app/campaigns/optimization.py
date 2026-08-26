"""Deterministic parameter-space sampling used by campaign-backed studies."""

import hashlib
import importlib
import itertools
import random
from dataclasses import dataclass
from typing import Any, Literal, cast

ParameterKind = Literal["integer", "float", "categorical", "boolean"]
DEFAULT_PARAMETER_SPACE: dict[str, list[int]] = {
    "short_window": [2, 3, 5, 8],
    "long_window": [5, 8, 13, 21],
}


@dataclass(frozen=True)
class ParameterDefinition:
    name: str
    kind: ParameterKind
    values: tuple[int | float | str | bool, ...]


class ParameterSpace:
    """Validated finite space. Workers receive only a chosen immutable mapping."""

    def __init__(
        self, definitions: list[ParameterDefinition], constraints: list[dict[str, Any]]
    ) -> None:
        if not definitions:
            raise ValueError("parameter space must contain at least one parameter")
        if len({item.name for item in definitions}) != len(definitions):
            raise ValueError("parameter names must be unique")
        if any(not item.values for item in definitions):
            raise ValueError("each parameter must have at least one possible value")
        self.definitions, self.constraints = definitions, constraints

    @classmethod
    def from_raw(cls, raw: dict[str, Any] | None) -> "ParameterSpace":
        raw = raw or DEFAULT_PARAMETER_SPACE
        constraints = list(raw.get("__constraints__", [])) if "__constraints__" in raw else []
        return cls(
            [_definition(name, spec) for name, spec in raw.items() if name != "__constraints__"],
            constraints,
        )

    def as_dict(self) -> dict[str, Any]:
        payload = {
            item.name: {"type": item.kind, "values": list(item.values)} for item in self.definitions
        }
        return payload | ({"__constraints__": self.constraints} if self.constraints else {})

    def candidates(self) -> list[dict[str, int | float | str | bool]]:
        names = [item.name for item in self.definitions]
        candidates = [
            dict(zip(names, values, strict=True))
            for values in itertools.product(*(item.values for item in self.definitions))
        ]
        return [item for item in candidates if not self.rejection_reasons(item)]

    def rejection_reasons(self, parameters: dict[str, Any]) -> list[str]:
        reasons: list[str] = []
        if {"short_window", "long_window"} <= parameters.keys() and int(
            parameters["short_window"]
        ) >= int(parameters["long_window"]):
            reasons.append("short_window must be less than long_window")
        for rule in self.constraints:
            left, right, operator = rule.get("left"), rule.get("right"), rule.get("operator")
            if left not in parameters or right not in parameters:
                reasons.append("constraint references an unknown parameter")
            elif operator == "<" and not parameters[left] < parameters[right]:
                reasons.append(f"{left} must be less than {right}")
            elif operator == "<=" and not parameters[left] <= parameters[right]:
                reasons.append(f"{left} must be less than or equal to {right}")
            elif operator not in {"<", "<="}:
                reasons.append("constraint operator must be < or <=")
        return reasons


def generate_parameter_variants(
    parameter_space: dict[str, Any] | None, method: str, max_variants: int, seed: int = 17
) -> list[dict[str, int | float | str | bool]]:
    space = ParameterSpace.from_raw(parameter_space)
    candidates = space.candidates()
    if method == "grid":
        variants = candidates
    elif method == "random":
        variants = list(candidates)
        random.Random(seed).shuffle(variants)
    elif method == "bayesian":
        variants = _optuna_search(space, max_variants, seed)
    else:
        raise ValueError("optimization method must be grid, random, or bayesian")
    return _unique(variants)[:max_variants]


def candidate_rejection_reasons(
    parameter_space: dict[str, Any] | None, parameters: dict[str, Any]
) -> list[str]:
    return ParameterSpace.from_raw(parameter_space).rejection_reasons(parameters)


def parameter_hash(parameters: dict[str, Any]) -> str:
    return hashlib.sha256(repr(sorted(parameters.items())).encode()).hexdigest()


def idempotency_key(campaign_id: str, symbol: str, parameters: dict[str, Any]) -> str:
    return hashlib.sha256(
        f"{campaign_id}:{symbol}:{parameter_hash(parameters)}".encode()
    ).hexdigest()[:32]


def _definition(name: str, spec: Any) -> ParameterDefinition:
    if not isinstance(spec, dict):
        values = tuple(spec)
        return ParameterDefinition(name, _infer_kind(values), values)
    kind = str(spec.get("type", "integer"))
    if kind not in {"integer", "float", "categorical", "boolean"}:
        raise ValueError(f"{name}: unsupported parameter type {kind}")
    if kind == "boolean":
        return ParameterDefinition(name, "boolean", (False, True))
    if kind == "categorical":
        return ParameterDefinition(name, "categorical", tuple(spec.get("values", [])))
    if "min" not in spec or "max" not in spec:
        raise ValueError(f"{name}: numeric parameters require min and max")
    start, end = spec["min"], spec["max"]
    if start > end:
        raise ValueError(f"{name}: min must not exceed max")
    step = spec.get("step", 1 if kind == "integer" else None)
    if step is None:
        values = (start, (float(start) + float(end)) / 2, end)
    elif float(step) <= 0:
        raise ValueError(f"{name}: step must be positive")
    elif kind == "integer":
        values = tuple(range(int(start), int(end) + 1, int(step)))
    else:
        values = tuple(
            round(float(start) + index * float(step), 12)
            for index in range(int(round((float(end) - float(start)) / float(step))) + 1)
        )
    return ParameterDefinition(name, cast(ParameterKind, kind), values)


def _infer_kind(values: tuple[Any, ...]) -> ParameterKind:
    if values and all(isinstance(value, bool) for value in values):
        return "boolean"
    if values and all(isinstance(value, int) and not isinstance(value, bool) for value in values):
        return "integer"
    if values and all(
        isinstance(value, (int, float)) and not isinstance(value, bool) for value in values
    ):
        return "float"
    return "categorical"


def _optuna_search(
    space: ParameterSpace, max_variants: int, seed: int
) -> list[dict[str, int | float | str | bool]]:
    try:
        optuna = importlib.import_module("optuna")
    except ModuleNotFoundError:
        return _diverse_candidates(space.candidates(), max_variants)
    sampler = optuna.samplers.TPESampler(seed=seed, n_startup_trials=max_variants)
    study = optuna.create_study(direction="maximize", sampler=sampler)
    proposals: list[dict[str, int | float | str | bool]] = []
    for _ in range(max_variants):
        trial = study.ask()
        parameters = {
            item.name: trial.suggest_categorical(item.name, list(item.values))
            for item in space.definitions
        }
        study.tell(trial, 0.0)  # proposal bookkeeping; real scores are persisted after backtests.
        if not space.rejection_reasons(parameters):
            proposals.append(parameters)
    return proposals


def _diverse_candidates(
    candidates: list[dict[str, int | float | str | bool]], max_variants: int
) -> list[dict[str, int | float | str | bool]]:
    if len(candidates) <= max_variants:
        return candidates
    if max_variants == 1:
        return [candidates[0]]
    return [
        candidates[round(index * (len(candidates) - 1) / (max_variants - 1))]
        for index in range(max_variants)
    ]


def _unique(
    items: list[dict[str, int | float | str | bool]],
) -> list[dict[str, int | float | str | bool]]:
    result, seen = [], set()
    for item in items:
        key = parameter_hash(item)
        if key not in seen:
            result.append(item)
            seen.add(key)
    return result
