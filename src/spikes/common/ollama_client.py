"""Calls to the local Ollama server, and reading its replies."""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

from config import OLLAMA_URL


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
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=1800) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        sys.exit(f"Could not reach Ollama at {OLLAMA_URL}. Is it running? ({e})")
    data["_wall_seconds"] = round(time.perf_counter() - start, 2)
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
        "thinking_chars": len(thinking),
        "thinking": thinking,
    }


def parse_json(raw: str):
    """Parse the model's reply. Returns (data, True), or (None, False) if it is not valid JSON."""
    try:
        return json.loads(raw), True
    except json.JSONDecodeError:
        return None, False
