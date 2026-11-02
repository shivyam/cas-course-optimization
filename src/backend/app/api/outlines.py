"""Course outline upload endpoint."""

from typing import Annotated

import pymupdf
from fastapi import APIRouter, File, HTTPException, UploadFile

router = APIRouter(tags=["outlines"])

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024


@router.post("/outlines")
async def upload_outline(file: Annotated[UploadFile, File()]) -> dict:
    """Validate a PDF course outline and return upload metadata."""
    # Check both the browser-provided type and the filename before reading the
    # upload so unsupported files fail with a clear client-facing response.
    filename = file.filename or ""
    if file.content_type != "application/pdf" or not filename.lower().endswith(".pdf"):
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
        document = pymupdf.open(stream=contents, filetype="pdf")
        text = "\n\n".join(page.get_text() for page in document).strip()
    except pymupdf.FileDataError as error:
        raise HTTPException(
            status_code=400, detail="The uploaded file is not a valid PDF."
        ) from error
    finally:
        # Always release PyMuPDF's document resources, including on parse errors.
        if "document" in locals():
            document.close()

    return {
        "filename": filename,
        "status": "received",
        "size_bytes": len(contents),
        "text_extraction": "pymupdf",
        "text": text,
    }
