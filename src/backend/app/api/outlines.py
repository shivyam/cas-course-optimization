"""Course outline upload endpoint (stub).

This endpoint only defines the request/response shape so the frontend can be
built against it. Real outline parsing is added in a later issue.
"""

from typing import Annotated

from fastapi import APIRouter, File, UploadFile

# Tags group endpoints together in the auto-generated docs at /docs.
router = APIRouter(tags=["outlines"])


@router.post("/outlines")
async def upload_outline(file: Annotated[UploadFile, File()]) -> dict:
    """Accept a course outline upload and return a fixed mock response.

    Stub only: the file is not stored or parsed. Real parsing is added in a
    later issue.
    """
    # The file must be sent as multipart/form-data under the field name "file".
    # FastAPI returns 422 automatically if it is missing.
    # Mock data below is placeholder only; it is not a real course.
    return {
        "filename": file.filename,
        "status": "received",
        "course": {
            "code": "COMPSCI 0000",
            "title": "Mock Course",
            "assessments": [
                {"name": "Midterm 1", "type": "midterm", "week": 6},
                {"name": "Assignment 1", "type": "assignment", "week": 4},
            ],
        },
    }
