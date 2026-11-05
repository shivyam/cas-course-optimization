"""Course outline upload endpoint."""

import os
import re
from pathlib import Path
from typing import Annotated

import pymupdf
from fastapi import APIRouter, File, HTTPException, UploadFile

router = APIRouter(tags=["outlines"])

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
DEFAULT_EXTRACTED_TEXT_DIR = (
    Path(__file__).resolve().parents[4] / "data" / "extracted_text"
)
EXTRACTED_TEXT_DIR = Path(
    os.getenv("EXTRACTED_TEXT_DIR", str(DEFAULT_EXTRACTED_TEXT_DIR))
)
EXTRACTED_TEXT_REPO_PATH = Path("data") / "extracted_text"
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/x-pdf",
    "application/octet-stream",
}


def extract_pdf_text(contents: bytes) -> str:
    """Extract text from a PDF's contents."""
    try:
        document = pymupdf.open(stream=contents, filetype="pdf")
        text = "\n\n".join(page.get_text() for page in document).strip()
    except pymupdf.FileDataError as error:
        raise ValueError("The uploaded file is not a valid PDF.") from error
    finally:
        if "document" in locals():
            document.close()
    return text


def save_extracted_text(filename: str, text: str) -> Path:
    """Save extracted text and return its path relative to the repository."""
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename).stem).strip("._")
    safe_stem = safe_stem or "outline"
    output_path = EXTRACTED_TEXT_DIR / f"{safe_stem}.txt"

    EXTRACTED_TEXT_DIR.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")

    return EXTRACTED_TEXT_REPO_PATH / output_path.name


@router.post("/outlines")
async def upload_outline(file: Annotated[UploadFile, File()]) -> dict:
    """Validate a PDF course outline and return upload metadata."""
    # Check both the browser-provided type and the filename before reading the
    # upload so unsupported files fail with a clear client-facing response.
    filename = file.filename or ""
    if (
        file.content_type not in ALLOWED_CONTENT_TYPES
        or not filename.lower().endswith(".pdf")
    ):
        raise HTTPException(status_code=415, detail="Only PDF files are supported.")

    # Read one byte beyond the limit so an oversized upload can be detected
    # without loading an unbounded request body into memory.
    contents = await file.read(MAX_FILE_SIZE_BYTES + 1)
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413, detail="PDF files must be 10 MB or smaller."
        )
    if not contents.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=400, detail="The uploaded file is not a valid PDF."
        )

    try:
        # PyMuPDF extracts text page by page and preserves page boundaries in
        # the response, which makes the preview easier to read.
        text = extract_pdf_text(contents)
    except ValueError as error:
        raise HTTPException(
            status_code=400, detail="The uploaded file is not a valid PDF."
        ) from error

    try:
        text_file = save_extracted_text(filename, text)
    except OSError as error:
        raise HTTPException(
            status_code=500, detail="Unable to save extracted outline text."
        ) from error

    return {
        "filename": filename,
        "status": "received",
        "size_bytes": len(contents),
        "text_extraction": "pymupdf",
        "text": text,
        "text_file": str(text_file),
    }
