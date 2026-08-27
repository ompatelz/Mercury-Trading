from datetime import datetime, timedelta

import polars as pl
import pytest

from app.strategy_dsl.compiler import (
    canonical_json,
    compile_strategy,
    evaluate_positions,
    strategy_hash,
)
from app.strategy_dsl.schemas import StrategySpec, moving_average_crossover_spec
from app.strategy_dsl.validation import StrategyValidationError, parse_strategy, validate_strategy


def test_canonical_hash_and_plan_are_deterministic() -> None:
    first = moving_average_crossover_spec({"fast_window": 10, "slow_window": 30})
    second = StrategySpec.model_validate(first.model_dump())
    assert canonical_json(first) == canonical_json(second)
    assert strategy_hash(first) == strategy_hash(second)
    assert compile_strategy(first).steps[-1] == "execute on next bar open"


def test_semantic_validation_rejects_unknown_reference_and_contradiction() -> None:
    payload = moving_average_crossover_spec({"fast_window": 10, "slow_window": 30}).model_dump()
    payload["entry"] = {
        "type": "comparison",
        "left": "missing",
        "operator": "gt",
        "right": "slow_ma",
    }
    with pytest.raises(StrategyValidationError, match="unknown indicator"):
        validate_strategy(parse_strategy(payload))

    payload["entry"] = payload["exit"]
    with pytest.raises(StrategyValidationError, match="identical"):
        validate_strategy(parse_strategy(payload))


def test_semantic_validation_rejects_inverted_crossover_windows() -> None:
    spec = moving_average_crossover_spec({"fast_window": 30, "slow_window": 10})
    with pytest.raises(StrategyValidationError, match="window must be less"):
        validate_strategy(spec)


def test_schema_forbids_future_data_and_unknown_properties() -> None:
    payload = moving_average_crossover_spec({"fast_window": 10, "slow_window": 30}).model_dump()
    payload["entry"] = {
        "type": "comparison",
        "left": "close[t+1]",
        "operator": "gt",
        "right": "slow_ma",
    }
    with pytest.raises(StrategyValidationError, match="unknown indicator"):
        validate_strategy(parse_strategy(payload))
    payload["python"] = "__import__('os').system('bad')"
    with pytest.raises(StrategyValidationError, match="Extra inputs are not permitted"):
        parse_strategy(payload)


def test_positions_use_only_completed_bars_and_trade_next_open() -> None:
    spec = moving_average_crossover_spec({"fast_window": 2, "slow_window": 3})
    start = datetime(2024, 1, 1)
    closes = [1.0, 1.0, 1.0, 10.0, 10.0]
    bars = pl.DataFrame(
        {
            "timestamp": [start + timedelta(days=index) for index in range(len(closes))],
            "open": closes,
            "close": closes,
        }
    )
    positions = evaluate_positions(spec, bars).get_column("position").to_list()
    assert positions[:4] == [0.0, 0.0, 0.0, 0.0]
    assert positions[4] == 1.0


def test_resource_limit_rejects_excessive_bars() -> None:
    payload = moving_average_crossover_spec({"fast_window": 2, "slow_window": 3}).model_dump()
    payload["risk_constraints"] = {"max_bars_processed": 2}
    spec = parse_strategy(payload)
    bars = pl.DataFrame({"close": [1.0, 2.0, 3.0]})
    with pytest.raises(StrategyValidationError, match="bar count"):
        evaluate_positions(spec, bars)
