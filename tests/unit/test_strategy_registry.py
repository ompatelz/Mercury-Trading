import pytest

from app.backtesting.registry import validate_strategy_spec


def test_strategy_registry_accepts_known_strategy() -> None:
    parameters = validate_strategy_spec(
        "moving_average_crossover",
        {"fast_window": 2, "slow_window": 3},
    )

    assert parameters == {"fast_window": 2, "slow_window": 3}


def test_strategy_registry_rejects_unknown_strategy() -> None:
    with pytest.raises(ValueError, match="unknown strategy"):
        validate_strategy_spec("arbitrary_python", {"fast_window": 2, "slow_window": 3})


def test_strategy_registry_rejects_invalid_parameters() -> None:
    with pytest.raises(ValueError, match="fast_window must be less than slow_window"):
        validate_strategy_spec(
            "moving_average_crossover",
            {"fast_window": 10, "slow_window": 3},
        )
