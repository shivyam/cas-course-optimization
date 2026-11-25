"""Course outline upload endpoint."""

import os
import re
from pathlib import Path
from typing import Annotated

import pymupdf
from fastapi import APIRouter, File, HTTPException, UploadFile

router = APIRouter(tags=["outlines"])

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
MAX_BATCH_FILES = 50
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


def save_extracted_text(filename: str, text: str) -> str:
    """Save extracted text and return its repo-relative path with POSIX separators."""
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename).stem).strip("._")
    safe_stem = safe_stem or "outline"
    output_path = EXTRACTED_TEXT_DIR / f"{safe_stem}.txt"

    EXTRACTED_TEXT_DIR.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")

    # Use POSIX separators so API responses stay stable across Windows and Unix.
    return (EXTRACTED_TEXT_REPO_PATH / output_path.name).as_posix()


async def process_outline_upload(file: UploadFile) -> dict:
    """Validate one PDF course outline and return upload metadata."""
    # Check both the browser-provided type and the filename before reading the
    # upload so unsupported files fail with a clear client-facing response.
    filename = file.filename or ""
    if file.content_type not in ALLOWED_CONTENT_TYPES or not filename.lower().endswith(
        ".pdf"
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


async def process_outline_upload_result(file: UploadFile) -> dict:
    """Process one upload and return a success or failure result object."""
    filename = file.filename or "unknown.pdf"
    try:
        result = await process_outline_upload(file)
        return {**result, "ok": True}
    except HTTPException as error:
        detail = error.detail
        if not isinstance(detail, str):
            detail = "The course outline could not be uploaded."
        return {
            "ok": False,
            "filename": filename,
            "status": "error",
            "detail": detail,
            "status_code": error.status_code,
        }


@router.post("/outlines")
async def upload_outline(file: Annotated[UploadFile, File()]) -> dict:
    """Validate a PDF course outline and return upload metadata."""
    return await process_outline_upload(file)


@router.post("/outlines/batch")
async def upload_outlines(
    files: Annotated[list[UploadFile], File(description="One or more PDF outlines")],
) -> dict:
    """Validate and extract text from many PDF course outlines at once."""
    if not files:
        raise HTTPException(status_code=400, detail="Select at least one PDF file.")
    if len(files) > MAX_BATCH_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Upload at most {MAX_BATCH_FILES} PDF files at once.",
        )

    results = [await process_outline_upload_result(file) for file in files]
    succeeded = sum(1 for result in results if result.get("ok"))
    failed = len(results) - succeeded

    return {
        "status": "completed",
        "total": len(results),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }
