"""Tests for the POST /api/outlines endpoint."""

import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.api import outlines
from app.cli import main as extract_course_outline
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


def test_upload_outline_extracts_text(tmp_path, monkeypatch):
    # The endpoint should return the text that was embedded in the PDF page.
    monkeypatch.setattr(outlines, "EXTRACTED_TEXT_DIR", tmp_path)
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

    # Save text to local files for testing purposes
    saved_files = list(tmp_path.glob("*.txt"))
    assert len(saved_files) == 1
    assert saved_files[0].name == "outline.txt"
    assert body["text_file"] == "data/extracted_text/outline.txt"
    assert saved_files[0].read_text(encoding="utf-8") == "Course outline text"


@pytest.mark.parametrize(
    "content_type",
    ["application/x-pdf", "application/octet-stream"],
)
def test_upload_outline_accepts_alternate_pdf_content_types(
    content_type, tmp_path, monkeypatch
):
    monkeypatch.setattr(outlines, "EXTRACTED_TEXT_DIR", tmp_path)
    files = {"file": ("outline.pdf", make_pdf("Course outline text"), content_type)}

    response = client.post("/api/outlines", files=files)

    assert response.status_code == 200
    assert response.json()["text"] == "Course outline text"


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


def test_cli_extracts_local_outline(tmp_path, monkeypatch, capsys):
    pdf_path = tmp_path / "course outline.pdf"
    pdf_path.write_bytes(make_pdf("CLI outline text"))
    output_dir = tmp_path / "extracted_text"
    monkeypatch.setattr(outlines, "EXTRACTED_TEXT_DIR", output_dir)
    monkeypatch.setattr("sys.argv", ["cas-extract-outline", str(pdf_path)])

    assert extract_course_outline() == 0

    output_path = output_dir / "course_outline.txt"
    assert output_path.read_text(encoding="utf-8") == "CLI outline text"
    assert (
        capsys.readouterr().out.strip()
        == (
            "Succesfully extracted course outline text to: "
            "data/extracted_text/course_outline.txt"
        )
    )
