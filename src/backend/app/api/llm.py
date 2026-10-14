"""Endpoints for testing a locally running language model."""

from typing import Annotated

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.llm_client import LLMClientError, generate_response

router = APIRouter(tags=["llm"])


class LLMRequest(BaseModel):
    """Prompt sent to the local model."""

    prompt: Annotated[str, Field(min_length=1, max_length=10_000)]


class LLMResponse(BaseModel):
    """Response returned by the local model."""

    response: str


@router.post("/llm/test", response_model=LLMResponse)
async def test_llm(request: LLMRequest) -> LLMResponse:
    """Send one prompt to the configured local model."""
    try:
        response = await generate_response(request.prompt)
    except LLMClientError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    return LLMResponse(response=response)
