"""Tests for GET /api/health."""

from fastapi.testclient import TestClient

from app.main import app

# TestClient calls the app in-process, so no server needs to be running.
client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/api/health")

    # The frontend relies on this exact response to show the backend is up.
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
