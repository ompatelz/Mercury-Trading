from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_security_headers_are_present(client: TestClient) -> None:
    response = client.get("/health")

    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_oversized_declared_request_is_rejected_before_route_processing(monkeypatch) -> None:
    monkeypatch.setenv("MAX_REQUEST_BODY_BYTES", "8")
    get_settings.cache_clear()
    app = create_app()
    with TestClient(app) as client:
        response = client.post("/campaigns", content=b"012345678")

    assert response.status_code == 413
    assert response.json() == {"detail": "request body too large"}
    get_settings.cache_clear()


def test_unexpected_errors_do_not_expose_exception_details() -> None:
    app = create_app()

    @app.get("/security-test-error")
    def security_test_error() -> None:
        raise RuntimeError("postgresql://user:credential@host/private")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/security-test-error")

    assert response.status_code == 500
    assert response.json() == {"detail": "internal server error"}
    assert "credential" not in response.text
