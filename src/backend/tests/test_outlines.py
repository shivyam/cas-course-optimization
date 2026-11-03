"""Tests for the POST /api/outlines endpoint."""

import pymupdf
from fastapi.testclient import TestClient

from app.main import app

# TestClient calls the app in-process, so no server needs to be running.
client = TestClient(app)


def make_pdf(text: str) -> bytes:
    # Generate a real in-memory PDF
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    contents = document.tobytes()
    document.close()
    return contents


def test_upload_outline_extracts_text():
    # The endpoint should return the text that was embedded in the PDF page.
    files = {
        "file": ("outline.pdf", make_pdf("Course outline text"), "application/pdf")
    }

    response = client.post("/api/outlines", files=files)

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "outline.pdf"
    assert body["status"] == "received"
    assert body["text_extraction"] == "pymupdf"
    assert body["text"] == "Course outline text"


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
