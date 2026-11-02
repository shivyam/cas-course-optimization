"""Tests for the POST /api/outlines endpoint."""

from fastapi.testclient import TestClient

from app.main import app

# TestClient calls the app in-process, so no server needs to be running.
client = TestClient(app)


def test_upload_outline_accepts_pdf():
    files = {"file": ("outline.pdf", b"%PDF-1.4 fake content", "application/pdf")}

    response = client.post("/api/outlines", files=files)

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "outline.pdf"
    assert body["status"] == "received"
    assert body["text_extraction"] == "not_configured"


def test_upload_outline_rejects_non_pdf():
    files = {"file": ("outline.txt", b"course outline", "text/plain")}

    response = client.post("/api/outlines", files=files)

    assert response.status_code == 415


def test_upload_outline_rejects_invalid_pdf_content():
    files = {"file": ("outline.pdf", b"not a pdf", "application/pdf")}

    response = client.post("/api/outlines", files=files)

    assert response.status_code == 400


def test_upload_outline_without_file_is_rejected():
    # No file attached, so FastAPI's request validation should reject it.
    response = client.post("/api/outlines")

    assert response.status_code == 422
