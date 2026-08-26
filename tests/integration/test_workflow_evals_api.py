from fastapi.testclient import TestClient


def test_workflow_eval_api_exposes_benchmarks_and_blocks_critical_regression(
    client: TestClient,
) -> None:
    versions = client.get("/evals/versions")
    assert versions.status_code == 200
    baseline_id = versions.json()["workflows"][0]["id"]

    benchmarks = client.get("/evals/benchmarks")
    assert benchmarks.status_code == 200
    assert len(benchmarks.json()[0]["tasks"]) == 8

    run = client.post("/evals/runs", json={"workflow_version_id": baseline_id})
    assert run.status_code == 201
