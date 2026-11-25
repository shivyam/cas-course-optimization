"""Calls to the local Ollama server, and reading its replies."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from config import OLLAMA_URL

# How often one call is tried when Ollama answers with a server error, and the wait between
SERVER_ERROR_TRIES = 4        # the first try plus 3 retries
RETRY_WAIT_SECONDS = 30


class OllamaError(Exception):
    """Ollama could not answer one call. spike_llm.py skips that outline run and goes on."""


def chat(model: str, messages: list[dict], num_ctx: int, schema: dict | None = None,
         num_predict: int | None = None, think: bool | None = None) -> dict:
    """One call to the local Ollama chat API. schema=None means free text.

    think: the model's own built-in reasoning mode (Qwen3 has one; Gemma and Llama runs
    never set it). None leaves it out of the request, which is how every Gemma and Llama
    run was made, so those results are unchanged. True or False sends Ollama's "think" field.
    """
    options = {"temperature": 0, "num_ctx": num_ctx}
    if num_predict:
        options["num_predict"] = num_predict
    body = {"model": model, "messages": messages, "stream": False, "options": options}
    if schema is not None:
        body["format"] = schema
    if think is not None:
        body["think"] = think
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    # A server error (HTTP 5xx) is retried a few times. On the shared CAS GPU server,
    # Ollama answered "500 Internal Server Error" now and then (#39 GPU findings), and one
    # error used to stop the whole run. At temperature 0 a retry gives the same answer
    # the first try would have, so retrying does not change the results.
    for attempt in range(1, SERVER_ERROR_TRIES + 1):
        start = time.perf_counter()
        try:
            # One hour per call: Qwen3 4B's think step took up to 27 min, and one call passed 30 min
            with urllib.request.urlopen(req, timeout=3600) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            # Ollama puts the reason in the body, e.g. {"error": "... out of memory"}
            reason = e.read().decode("utf-8", errors="replace")[:300]
            if e.code < 500:
                raise OllamaError(f"Ollama refused the request (HTTP {e.code}): {reason}") from e
            if attempt == SERVER_ERROR_TRIES:
                raise OllamaError(f"Ollama server error (HTTP {e.code}) {attempt} times in a row; "
                                  f"last reason: {reason}") from e
            print(f"  Ollama server error (HTTP {e.code}): {reason}")
            print(f"  RETRY {attempt}/{SERVER_ERROR_TRIES - 1} in {RETRY_WAIT_SECONDS} s ...", flush=True)
            time.sleep(RETRY_WAIT_SECONDS)
            continue
        except urllib.error.URLError as e:
            # Not reachable at all (Ollama stopped, tunnel closed): retrying will not help
            raise OllamaError(f"Could not reach Ollama at {OLLAMA_URL}. Is it running? ({e})") from e
        data["_wall_seconds"] = round(time.perf_counter() - start, 2)
        data["_retries"] = attempt - 1   # how many server errors came before this answer
        return data


def call_ollama(model: str, system: str, user: str, schema: dict, num_ctx: int,
                think: bool | None = None) -> dict:
    """Single-turn call: one system prompt, one user message, JSON reply."""
    return chat(model, [{"role": "system", "content": system}, {"role": "user", "content": user}],
                num_ctx, schema, think=think)


def step_meta(name: str, resp: dict) -> dict:
    """Keep what is needed from one Ollama reply: tokens read and written, timings, raw text.
    prompt_tokens is what the model actually read (used to spot a cut-off outline).
    thinking is the model's built-in reasoning text, if it returned any (Qwen3 with
    thinking on). Its tokens are included in output_tokens.
    """
    msg = resp.get("message", {})
    content = msg.get("content", "")
    thinking = msg.get("thinking") or ""
    # Some Ollama versions put the reasoning inside the reply as <think>...</think>.
    # Keep it, but take it out of raw so the JSON can still be parsed.
    if "<think>" in content and "</think>" in content:
        before, _, rest = content.partition("<think>")
        inline, _, after = rest.partition("</think>")
        thinking = thinking or inline.strip()
        content = (before + after).strip()
    return {
        "step": name,
        "prompt_tokens": resp.get("prompt_eval_count"),
        "output_tokens": resp.get("eval_count"),
        "seconds": resp.get("_wall_seconds"),
        "eval_seconds": round((resp.get("eval_duration") or 0) / 1e9, 2),
        "raw": content,
        "retries": resp.get("_retries", 0),   # server errors before this answer (0 = none)
        "thinking_chars": len(thinking),
        "thinking": thinking,
    }


def parse_json(raw: str):
    """Parse the model's reply. Returns (data, True), or (None, False) if it is not valid JSON."""
    try:
        return json.loads(raw), True
    except json.JSONDecodeError:
        return None, False
