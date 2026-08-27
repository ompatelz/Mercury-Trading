from fastapi.testclient import TestClient


def test_factor_research_api_compiles_and_evaluates_point_in_time_scores(
    client: TestClient,
) -> None:
    definition = {
        "factor_id": "momentum",
        "name": "Momentum",
        "version": "v1",
        "input_features": ["adjusted_close"],
        "lookback": 20,
        "transformation": "trailing_return",
    }
    payload = {
        "strategy": {
            "universe_id": "liquid-etfs-v1",
            "factors": [definition],
            "selection": "top_n",
            "top_n": 1,
        },
        "scores": {
            "momentum": [
                {"timestamp": "2024-01-01T00:00:00Z", "asset_id": "A", "score": 0.2},
                {"timestamp": "2024-01-01T00:00:00Z", "asset_id": "B", "score": 0.1},
            ]
        },
        "forward_returns": [
            {"timestamp": "2024-01-01T00:00:00Z", "asset_id": "A", "horizon": 1, "value": 0.02},
            {"timestamp": "2024-01-01T00:00:00Z", "asset_id": "B", "horizon": 1, "value": 0.01},
        ],
    }

    assert client.post("/factor-research/validate", json=payload).status_code == 200
    response = client.post("/factor-research/evaluate", json=payload)

    assert response.status_code == 200
    assert response.json()["weights"] == [
        {"timestamp": "2024-01-01T00:00:00+00:00", "asset_id": "A", "weight": 1.0}
    ]
