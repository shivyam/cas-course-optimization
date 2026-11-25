"""The structure the model must reply with, one Pydantic model per extraction step.

Each model does two jobs, so they can never drift apart:
  1. `ollama_schema(Model)` turns it into a real JSON Schema that Ollama uses to
     constrain the reply (the old spike sent an *example* file, which Ollama
     cannot enforce, so the reply could be malformed).
  2. `Model.model_validate_json(reply)` checks the reply.

The model is never asked for `source_page`, `id` or the filename: the extractor
fills those in itself (see extractor.py). Everything else mirrors
`src/backend/helper/outline-text-structure.json`.

Note: class docstrings and Field descriptions end up in the JSON Schema sent to
the model, so they are written as short hints for the model to read.
"""

from __future__ import annotations

import copy

from pydantic import BaseModel, ConfigDict, Field

# Every model forbids unknown keys, so a reply with invented fields is rejected.
STRICT = ConfigDict(extra="forbid")

# Shared hint for every quote. The highlighting step searches the PDF for this
# exact text, so a reworded quote cannot be highlighted.
QUOTE = "Copied word for word from the outline. Never reworded."

# Fields typed `X | None` with no default are still *required*: the model must
# write them, as null when the outline does not say. That way a missing value
# is reported as missing instead of silently left out.


class Passage(BaseModel):
    """A quoted line from the outline (used for office hours)."""

    model_config = STRICT
    source_text: str = Field(description=QUOTE)


# --- Step 1: course header -------------------------------------------------


class Website(BaseModel):
    """The main course website and the line that names it."""

    model_config = STRICT
    link: str
    source_text: str = Field(description=QUOTE)


class Contact(BaseModel):
    """One instructor."""

    model_config = STRICT
    instructor: str
    email: str | None
    source_text: str = Field(description=QUOTE)

    # Required and not nullable on purpose: when it was allowed to be null,
    # Gemma always wrote null, even with the office hours line right there.
    # Forced to fill it in, it finds the line. "" means there is none; the
    # extractor turns that into null in the output.
    office_hours: Passage = Field(
        description='The "Office hours" line for this instructor; '
        'source_text "" if there is none.'
    )


class Header(BaseModel):
    """Course header: term, code, title, website and instructors."""

    model_config = STRICT
    # A list because some courses run in more than one term.
    term: list[str]
    course_code: str | None
    course_title: str | None
    website: Website | None
    contact: list[Contact]


# --- Step 2: sections, lectures, tutorials, TAs ----------------------------


class Lecture(BaseModel):
    """One lecture time line."""

    model_config = STRICT
    has_location: bool
    source_text: str = Field(description=QUOTE)


class Tutorial(BaseModel):
    """One tutorial or lab time line."""

    model_config = STRICT
    section: str | None
    has_location: bool
    source_text: str = Field(description=QUOTE)


class TeachingAssistant(BaseModel):
    """One teaching assistant line."""

    model_config = STRICT
    has_ta_info: bool
    source_text: str = Field(description=QUOTE)


class Section(BaseModel):
    """One lecture section (e.g. C01) and its meetings."""

    model_config = STRICT
    section: str
    lectures: list[Lecture]
    tutorials: list[Tutorial]
    teaching_assistants: list[TeachingAssistant]


class Sections(BaseModel):
    """All lecture sections of the course."""

    model_config = STRICT
    sections: list[Section]


# --- Step 3: assessments ---------------------------------------------------


class Assessment(BaseModel):
    """One graded item."""

    model_config = STRICT
    name: str
    # Free text, not a fixed list: the reference outlines use types such as
    # "deliverable" and "demonstration". The prompt suggests the usual ones.
    type: str
    source_text: str = Field(description=QUOTE)
    # Checked again in code (extractor._iso_date): anything else becomes null.
    date: str | None = Field(description="YYYY-MM-DD, or null if no full date")
    weight_percent: float | None


class Assessments(BaseModel):
    """Every graded item in the course."""

    model_config = STRICT
    assessments: list[Assessment]


# --- Step 4: materials and policies ----------------------------------------
# Each of these is "is it there, and where": a yes/no plus the line to highlight.


class Materials(BaseModel):
    """Required textbooks, materials or fees."""

    model_config = STRICT
    has_materials: bool
    source_text: str = Field(description=QUOTE + " Empty if not present.")


class GenAIPolicy(BaseModel):
    """The course's generative AI policy."""

    model_config = STRICT
    has_genai: bool
    source_text: str = Field(description=QUOTE + " Empty if not present.")


class AdvisoryPolicy(BaseModel):
    """The university's approved advisory statements."""

    model_config = STRICT
    has_advisory: bool
    source_text: str = Field(description=QUOTE + " Empty if not present.")


class DiscriminationPolicy(BaseModel):
    """The statement on discrimination, harassment or equity."""

    model_config = STRICT
    has_discrimination: bool
    source_text: str = Field(description=QUOTE + " Empty if not present.")


class MaterialsAndPolicies(BaseModel):
    """Materials plus the three policies, asked for in one call."""

    model_config = STRICT
    materials: Materials
    genai: GenAIPolicy
    advisory: AdvisoryPolicy
    discrimination: DiscriminationPolicy


# --- Step 5: learning outcomes and graduate attributes ---------------------


class LearningOutcome(BaseModel):
    """One learning outcome (or objective)."""

    model_config = STRICT
    # The outcome text is itself the quote that gets highlighted.
    text: str = Field(description=QUOTE)


class GraduateAttribute(BaseModel):
    """One graduate attribute listed in the outline."""

    model_config = STRICT
    code: str
    name: str
    level: str
    source_text: str = Field(description=QUOTE)


class Outcomes(BaseModel):
    """Learning outcomes and graduate attributes."""

    model_config = STRICT
    learning_outcomes: list[LearningOutcome]
    graduate_attributes: list[GraduateAttribute]


def ollama_schema(model: type[BaseModel]) -> dict:
    """JSON Schema for `model` with every $ref inlined.

    Pydantic puts nested models under $defs and points to them with $ref;
    inlining keeps the schema simple for Ollama's grammar converter.
    """
    schema = model.model_json_schema()
    # The named sub-schemas, e.g. {"Website": {...}, "Contact": {...}}.
    defs = schema.pop("$defs", {})

    def inline(node):
        """Walk the schema and replace each {"$ref": ...} with its definition."""
        if isinstance(node, dict):
            if "$ref" in node:
                # "#/$defs/Website" -> "Website"
                name = node["$ref"].split("/")[-1]
                # Copy so the same definition can be inlined in several places.
                return inline(copy.deepcopy(defs[name]))
            return {key: inline(value) for key, value in node.items()}
        if isinstance(node, list):
            return [inline(item) for item in node]
        return node

    return inline(schema)
