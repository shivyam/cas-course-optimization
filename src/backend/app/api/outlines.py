"""Course outline upload endpoint."""

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile

router = APIRouter(tags=["outlines"])

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024


@router.post("/outlines")
async def upload_outline(file: Annotated[UploadFile, File()]) -> dict:
    """Validate a PDF course outline and return upload metadata."""
    filename = file.filename or ""
    if file.content_type != "application/pdf" or not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Only PDF files are supported.")

    contents = await file.read(MAX_FILE_SIZE_BYTES + 1)
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413, detail="PDF files must be 10 MB or smaller."
        )
    if not contents.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=400, detail="The uploaded file is not a valid PDF."
        )

    return {
        "filename": filename,
        "status": "received",
        "size_bytes": len(contents),
        "text_extraction": "not_configured",
    }
