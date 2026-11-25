"""The five extraction steps and how the model is asked for each one.

Each step is one model call with its own task prompt, JSON Schema and token
limit. run_step sends it, checks the reply against the schema, and retries once
at a slightly higher temperature if the reply is cut off or does not fit.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel, ValidationError

from app.extraction import llm_client, prompts
from app.extraction.report import ExtractionReport
from app.extraction.schemas import (
    Assessments,
    Header,
    MaterialsAndPolicies,
    Outcomes,
    Sections,
    ollama_schema,
)

# A function that sends one request to the model, with the same arguments as
# llm_client.complete. The real one is used by default; tests pass a fake.
ModelCall = Callable[..., llm_client.Completion]


class InvalidModelOutputError(Exception):
    """The model's reply did not fit the expected structure, even after a retry."""

    def __init__(self, step_name: str, reason: str, reply_text: str):
        super().__init__(f"Step '{step_name}': {reason}")

        # Which step failed (e.g. "assessments"), so the CLI can name the file.
        self.step_name = step_name

        # The model's last reply, saved by the CLI so it can be inspected.
        self.reply_text = reply_text


@dataclass(frozen=True)
class Step:
    """One model call: what to ask, what shape the answer must have, and limits."""

    # Short name, used in the report and in error messages.
    name: str

    # The step's instructions, from prompts.py.
    task_prompt: str

    # The structure the reply must match, from schemas.py.
    reply_schema: type[BaseModel]

    # Reply length limit in tokens (hidden thinking included).
    max_tokens: int

    # Turn on the model's hidden reasoning. Only used where it measurably
    # helps, because it is several times slower.
    think: bool = False


# Token limits are a few times what a normal reply needs, so a reply that hits
# the limit is almost certainly looping. The thinking step needs room to reason.
STEPS = [
    Step(
        name="header",
        task_prompt=prompts.HEADER,
        reply_schema=Header,
        max_tokens=800,
    ),
    Step(
        name="sections",
        task_prompt=prompts.SECTIONS,
        reply_schema=Sections,
        max_tokens=1500,
    ),
    Step(
        # Thinking on: without it Gemma 4 E2B returned "Assignments" as one row
        # on Hellings 2CO3; with it, all 8 assignments with the right dates.
        name="assessments",
        task_prompt=prompts.ASSESSMENTS,
        reply_schema=Assessments,
        max_tokens=8000,
        think=True,
    ),
    Step(
        name="materials_policies",
        task_prompt=prompts.MATERIALS_POLICIES,
        reply_schema=MaterialsAndPolicies,
        max_tokens=800,
    ),
    Step(
        name="outcomes",
        task_prompt=prompts.OUTCOMES,
        reply_schema=Outcomes,
        max_tokens=2000,
    ),
]

# Temperature 0 always gives the same reply, so retrying at 0 would just repeat
# the same mistake. A little randomness gives the retry a real second chance.
FIRST_TRY_TEMPERATURE = 0.0
RETRY_TEMPERATURE = 0.3


def run_step(
    step: Step, outline_text: str, call_model: ModelCall, report: ExtractionReport
) -> BaseModel:
    """Ask the model for one step and return its checked reply.

    Tries twice. Raises InvalidModelOutputError if both replies are unusable.
    """
    # The outline goes in its own message, between <<< >>> markers, so the
    # model can see exactly where it starts and ends. This message is the same
    # for every step, which lets Ollama reuse it instead of re-reading it.
    outline_message = f"Course outline text:\n<<<\n{outline_text}\n>>>"
    json_schema = ollama_schema(step.reply_schema)

    # Filled in by each failed attempt, for the error message at the end.
    failure_reason = ""
    reply_text = ""

    attempts = [(1, FIRST_TRY_TEMPERATURE), (2, RETRY_TEMPERATURE)]
    for attempt_number, temperature in attempts:
        start_time = time.perf_counter()
        reply = call_model(
            prompts.COMMON,
            outline_message,
            task=step.task_prompt,
            schema=json_schema,
            max_tokens=step.max_tokens,
            temperature=temperature,
            think=step.think,
        )
        seconds_taken = round(time.perf_counter() - start_time, 2)

        # Record every attempt, so slow or retried steps show up in the report.
        report.model_calls.append(
            {
                "step": step.name,
                "attempt": attempt_number,
                "seconds": seconds_taken,
                "prompt_tokens": reply.prompt_tokens,
                "output_tokens": reply.output_tokens,
            }
        )
        reply_text = reply.text

        # A cut-off reply is never valid JSON, so there is no point parsing it.
        if reply.hit_token_limit:
            failure_reason = (
                f"reply cut off at {step.max_tokens} tokens (likely looping)"
            )
            continue

        # Parse the JSON and check every field against the schema.
        try:
            return step.reply_schema.model_validate_json(reply_text)
        except ValidationError as error:
            # Keep the first few problems only; the full list can be very long.
            failure_reason = f"reply does not fit the schema: {error.errors()[:3]}"

    raise InvalidModelOutputError(step.name, failure_reason, reply_text)
