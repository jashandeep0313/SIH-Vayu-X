"""Smoke tests — verify the app boots and basic routes respond."""

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_root_returns_service_metadata():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "vayux-backend"


def test_version_endpoint():
    response = client.get("/api/v1/version")
    assert response.status_code == 200
    assert response.json()["problem_statement"] == "26070"


def test_openapi_schema_generates():
    """Catches malformed route signatures and broken response models early."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/api/v1/cyclones" in response.json()["paths"]
