"""LLM Client module: the only code that knows which model is used and how it is called.

The model runs locally (on CAS servers in production) through Ollama, so no
outline text leaves CAS infrastructure. Swapping the model means changing the
LLM_MODEL environment variable, not any other module.

Settings (environment variables, with defaults):
    OLLAMA_URL      http://127.0.0.1:11435 (GPU tunnel; 11434 is local Ollama)
    LLM_MODEL       gemma4:e2b
    LLM_NUM_CTX     16384   context window in tokens (outline + instructions + reply)
    LLM_TIMEOUT_S   600     seconds to wait for one reply

To use the CAS GPU server instead of your laptop, run
src/backend/scripts/gpu_ollama.sh and set OLLAMA_URL=http://localhost:11435.
"""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load the environment file once when the backend imports
# this client.
REPO_ROOT = Path(__file__).resolve().parents[4]
load_dotenv(REPO_ROOT / ".env")

# We call Ollama's HTTP API with the standard library (urllib) on purpose, so
# the backend needs no extra package just to talk to the model.


class ModelUnavailableError(Exception):
    """Ollama could not be reached, or the model is not installed."""


class ModelTimeoutError(Exception):
    """The model did not reply in time."""


@dataclass
class Completion:
    """One model reply plus the numbers needed to spot problems."""

    # The reply text (JSON when a schema was given).
    text: str
    # How many tokens the model actually read. If this is close to the context
    # size, Ollama probably cut off the start of the outline.
    prompt_tokens: int | None
    # How many tokens the model wrote, including hidden thinking tokens.
    output_tokens: int | None
    # True when the reply stopped because it reached max_tokens, i.e. it was
    # cut off (usually a sign the model was looping).
    hit_token_limit: bool


@dataclass
class Settings:
    """Where the model runs and how it is called (see the top of this file)."""

    ollama_url: str
    model_name: str
    # Context window in tokens: outline + instructions + reply must fit in it.
    context_size: int
    timeout_seconds: float


def settings() -> Settings:
    """Read the settings from the environment variables.

    Read at call time, not import time, so tests and deployments can change
    the environment variables without restarting Python.
    """
    return Settings(
        # Strip a trailing "/" so f"{url}/api/chat" never has a double slash.
        ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/"),
        model_name=os.getenv("LLM_MODEL", "gemma4:e2b"),
        context_size=int(os.getenv("LLM_NUM_CTX", "16384")),
        timeout_seconds=float(os.getenv("LLM_TIMEOUT_S", "600")),
    )


def complete(
    instructions: str,
    data: str,
    task: str | None = None,
    schema: dict | None = None,
    max_tokens: int = 1000,
    temperature: float = 0.0,
    think: bool = False,
) -> Completion:
    """Send instructions and outline text to the model and return its reply.

    Args:
        instructions: rules shared by every call (sent as the system message).
        data: the outline text. Sent as its own message so it is always
            treated as data, never as instructions (prompt-injection defence).
        task: optional final message with the instructions for this call.
            Putting it after the outline keeps the start of every call
            identical, so Ollama can reuse the outline it already read.
        schema: optional JSON Schema. Ollama then only lets the model write
            JSON that fits it.
        max_tokens: hard limit on reply length (thinking included).
        temperature: 0 gives repeatable replies; the extractor raises it only
            for a retry, so the retry does not repeat the same mistake.
        think: turn on the model's hidden reasoning (Gemma 4, Qwen3). It helps
            on hard steps, but its tokens count against max_tokens.

    Raises:
        ModelUnavailableError: Ollama is not running or the model is missing.
        ModelTimeoutError: no reply within LLM_TIMEOUT_S seconds.
    """
    config = settings()
    url = config.ollama_url
    model = config.model_name
    timeout = config.timeout_seconds

    # Request body for Ollama's /api/chat endpoint.
    body = {
        "model": model,
        # One complete reply instead of a stream of pieces: simpler to handle.
        "stream": False,
        # Gemma 4 "thinks" by default. Left on everywhere, the hidden thinking
        # tokens used up max_tokens and cut the JSON off, so callers opt in.
        "think": think,
        "options": {
            "temperature": temperature,
            # Ollama's default context (4096) is too small for an outline.
            "num_ctx": config.context_size,
            # Ollama calls the reply length limit "num_predict".
            "num_predict": max_tokens,
        },
        # Message order: shared rules, then the outline, then (below) the task.
        "messages": [
            {"role": "system", "content": instructions},
            {"role": "user", "content": data},
        ],
    }
    if task:
        body["messages"].append({"role": "user", "content": task})
    if schema is not None:
        # "format" makes Ollama constrain the reply to this JSON Schema.
        body["format"] = schema

    request = urllib.request.Request(
        f"{url}/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            reply = json.loads(response.read().decode("utf-8"))
    except TimeoutError as error:
        # The server accepted the request but took too long to answer.
        raise ModelTimeoutError(f"No reply from {model} within {timeout}s.") from error
    except urllib.error.HTTPError as error:
        # Ollama answers 404 when the model is not pulled.
        raise ModelUnavailableError(f"Ollama refused the request: {error}") from error
    except urllib.error.URLError as error:
        # urllib wraps some timeouts in URLError, so check the real reason.
        if isinstance(error.reason, (TimeoutError, socket.timeout)):
            raise ModelTimeoutError(
                f"No reply from {model} within {timeout}s."
            ) from error
        # Anything else (connection refused, bad host) means no Ollama to talk to.
        raise ModelUnavailableError(
            f"Could not reach Ollama at {url}: {error}"
        ) from error

    # Keep only what the rest of the code needs from Ollama's reply.
    return Completion(
        text=reply.get("message", {}).get("content", ""),
        prompt_tokens=reply.get("prompt_eval_count"),
        output_tokens=reply.get("eval_count"),
        # Ollama sets done_reason to "length" when max_tokens stopped the reply.
        hit_token_limit=reply.get("done_reason") == "length",
    )


def is_available() -> bool:
    """True when Ollama is reachable and the configured model is installed."""
    config = settings()
    try:
        # /api/tags lists the models that have been pulled. 15 s, not less:
        # through the SSH tunnel to the GPU server, a 5 s limit once failed
        # while the server was busy, although it was running fine.
        tags_url = f"{config.ollama_url}/api/tags"
        with urllib.request.urlopen(tags_url, timeout=15) as response:
            tags = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError):
        return False
    installed_models = {model.get("name") for model in tags.get("models", [])}

    # "gemma4:e2b" is listed as is; a name without a tag is listed as ":latest".
    wanted = config.model_name
    return wanted in installed_models or f"{wanted}:latest" in installed_models
