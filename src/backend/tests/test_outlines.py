"""Tests for the POST /api/outlines stub."""

from fastapi.testclient import TestClient

from app.main import app

# TestClient calls the app in-process, so no server needs to be running.
client = TestClient(app)


def test_upload_outline_returns_mock_response():
    # Fake PDF bytes; the stub never reads the content, only the filename.
    files = {"file": ("outline.pdf", b"%PDF-1.4 fake content", "application/pdf")}

    response = client.post("/api/outlines", files=files)

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "outline.pdf"
    assert body["status"] == "received"
    assert len(body["course"]["assessments"]) > 0


def test_upload_outline_without_file_is_rejected():
    # No file attached, so FastAPI's request validation should reject it.
    response = client.post("/api/outlines")

    assert response.status_code == 422
