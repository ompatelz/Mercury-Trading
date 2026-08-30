def test_metrics_correlation_and_readiness(client) -> None:
    response = client.get("/health", headers={"X-Correlation-ID": "trace-123"})
    assert response.headers["X-Correlation-ID"] == "trace-123"
    assert "mercury_http_requests_total" in client.get("/metrics").text
    assert client.get("/readyz").json()["status"] == "ready"
