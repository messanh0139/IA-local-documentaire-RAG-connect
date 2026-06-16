from fastapi.testclient import TestClient

from app.main import app


def test_root_returns_operational_links() -> None:
    response = TestClient(app).get("/")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["docs"] == "/docs"


def test_security_headers_are_present() -> None:
    response = TestClient(app).get("/health")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
