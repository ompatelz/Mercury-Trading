from scripts.profile_system import profile


def test_profile_reports_measured_and_explicitly_unmeasured_surfaces() -> None:
    result = profile(rows=100, repeats=1)

    assert result["schema_version"] == 1
    assert {item["name"] for item in result["results"]} == {
        "api_health",
        "backtest_python",
        "strategy_dsl_positions",
        "optimization_grid_generation",
        "monte_carlo_bootstrap",
        "json_serialization",
    }
    assert "database" in result["not_measured"]
    assert all(item["median_ms"] >= 0 for item in result["results"])
