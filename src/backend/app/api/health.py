"""Health check endpoint.

Used by the frontend landing page (and anyone debugging) to confirm the
backend is running and reachable.
"""

from fastapi import APIRouter

# Tags group endpoints together in the auto-generated docs at /docs.
router = APIRouter(tags=["health"])


@router.get("/health")
def get_health() -> dict[str, str]:
    """Report that the API is running."""
    # No dependencies are checked yet (e.g. database); add them here when they exist.
    return {"status": "ok"}
