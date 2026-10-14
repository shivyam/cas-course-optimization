"""Entry point for the FastAPI backend.

Run locally from `src/backend` with:
    uvicorn app.main:app --reload
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, llm, outlines


def get_cors_origins() -> list[str]:
    """Read allowed CORS origins from the comma-separated CORS_ORIGINS variable."""
    # Default to the Vite dev server so the frontend works without extra setup.
    raw = os.getenv("CORS_ORIGINS", "http://localhost:5173")
    # Split on commas and drop blanks, e.g. "a, b," -> ["a", "b"].
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app = FastAPI(title="CAS Course Optimization API", version="0.1.0")

# Allow the frontend (served from a different port in development) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register every router under /api so all backend routes share one prefix,
# which is what the frontend dev proxy forwards to.
app.include_router(health.router, prefix="/api")
app.include_router(llm.router, prefix="/api")
app.include_router(outlines.router, prefix="/api")
