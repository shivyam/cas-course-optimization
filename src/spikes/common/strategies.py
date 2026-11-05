"""How the model is asked: baseline (one call) and think (notes first, then JSON).

Copied unchanged from the #38 Gemma spike. linking and fewshot were dropped for the
model comparison (see the #38 findings); they are still on branch spike/gemma4.
"""

from __future__ import annotations

from ollama_client import call_ollama, chat, parse_json, step_meta
from prompts import ASSESSMENT_SCHEMA, ASSESSMENT_SYSTEM, THINK_SYSTEM, THINK_TASK

STRATEGIES = ["baseline", "think"]


def strategy_think(text: str, args) -> tuple[dict | None, list[dict]]:
    """think strategy, two calls.

    Call 1: the model writes free-text notes (grading scheme, the lines that date each
    item, then a final list). Call 2: the notes plus the start of the outline (for course
    code and term) are turned into JSON with the normal extraction rules.
    """
    steps = []
    r1 = chat(args.model, [
        {"role": "system", "content": THINK_SYSTEM},
        {"role": "user", "content": f"Course outline text:\n<<<\n{text}\n>>>\n\n{THINK_TASK}"},
    ], args.num_ctx, None, num_predict=2500)
    steps.append(step_meta("think: reason over outline", r1))
    notes = steps[-1]["raw"]
    header = text[:1500]
    r2 = chat(args.model, [
        {"role": "system", "content": ASSESSMENT_SYSTEM},
        {"role": "user", "content": (
            f"Start of the course outline (for course code and term):\n<<<\n{header}\n>>>\n\n"
            f"Notes already made about this outline's assessments:\n<<<\n{notes}\n>>>\n\n"
            "Convert the final list in the notes into JSON. One row per individual item."
        )},
    ], args.num_ctx, ASSESSMENT_SCHEMA)
    steps.append(step_meta("think: notes to JSON", r2))
    parsed, _ = parse_json(steps[-1]["raw"])
    return parsed, steps


def run_strategy(text: str, args) -> tuple[dict | None, list[dict]]:
    """Run the chosen strategy and return (parsed JSON or None, list of model steps).
    baseline is a single call: the whole outline in, the full JSON out.
    """
    if args.strategy == "think":
        return strategy_think(text, args)
    # baseline
    r = call_ollama(args.model, ASSESSMENT_SYSTEM, f"Course outline text:\n<<<\n{text}\n>>>",
                    ASSESSMENT_SCHEMA, args.num_ctx)
    steps = [step_meta("baseline", r)]
    parsed, _ = parse_json(steps[-1]["raw"])
    return parsed, steps
