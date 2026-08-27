def _payload() -> dict[str, object]:
    return {
        "indicators": {
            "fast_ma": {"type": "sma", "window": 10},
            "slow_ma": {"type": "sma", "window": 30},
        },
        "entry": {"type": "comparison", "left": "fast_ma", "operator": "gt", "right": "slow_ma"},
        "exit": {"type": "comparison", "left": "fast_ma", "operator": "lt", "right": "slow_ma"},
        "position_sizing": {"value": 1.0},
    }


def test_strategy_validation_create_and_explain(client) -> None:
    validated = client.post("/strategies/validate", json=_payload())
    assert validated.status_code == 200
    assert validated.json()["valid"] is True
    created = client.post("/strategies", json=_payload())
    assert created.status_code == 201
    record = created.json()
    explained = client.get(f"/strategies/{record['id']}/explain")
    assert explained.status_code == 200
    assert record["strategy_hash"] in explained.json()["explanation"]


def test_invalid_strategy_is_reported_without_persistence(client) -> None:
    payload = _payload()
    payload["entry"] = {
        "type": "comparison",
        "left": "future_close",
        "operator": "gt",
        "right": "slow_ma",
    }
    response = client.post("/strategies/validate", json=payload)
    assert response.status_code == 200
    assert response.json()["valid"] is False
