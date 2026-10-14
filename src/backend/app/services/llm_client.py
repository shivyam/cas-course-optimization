"""Client for a locally running Ollama model."""

import os
import re

import httpx
from ollama import AsyncClient, RequestError, ResponseError


class LLMClientError(RuntimeError):
    """Raised when the local model cannot produce a response."""


def _ollama_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")


def _ollama_model() -> str:
    return os.getenv("OLLAMA_MODEL", "qwen3:4b")


def _ollama_timeout_seconds() -> float:
    return float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "480"))


def _final_response(content: str) -> str:
    """Return final model content without LLM reasoning."""
    if "</think>" in content:
        content = content.rsplit("</think>", maxsplit=1)[1]
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
    return content.strip()


async def generate_response(prompt: str) -> str:
    """Generate a response from the configured local Ollama model."""
    timeout_seconds = _ollama_timeout_seconds()
    try:
        client = AsyncClient(host=_ollama_url(), timeout=timeout_seconds)
        response = await client.chat(
            model=_ollama_model(),
            think=False,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract assessment names and weights "
                        "from course outline text. Return only the extracted "
                        "assessments and weights, with no reasoning, explanation, "
                        "markdown, or XML tags. Do not invent information that is "
                        "not provided."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
    except httpx.TimeoutException as error:
        raise LLMClientError(
            f"Ollama did not respond within {timeout_seconds:g} seconds using model "
            f"{_ollama_model()}."
        ) from error
    except (ConnectionError, RequestError, ResponseError) as error:
        raise LLMClientError(
            "Could not reach Ollama. Make sure it is running and the configured "
            f"model ({_ollama_model()}) is available."
        ) from error

    generated_text = _final_response(response.message.content)
    if not generated_text:
        raise LLMClientError("Ollama returned a response with an invalid format.")

    return generated_text
