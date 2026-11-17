"""Tests for the LLM extraction package (app/extraction).

No model is called: a fake model returns canned JSON replies, so these run in
CI without Ollama. They check the parts our code owns: the schema sent to
Ollama, reply checking and retry, page lookup for traceability, ids, dates,
and that the output matches outline-text-structure.json.
"""

import json
from pathlib import Path

import pytest

from app.extraction.extractor import (
    STEPS,
    ExtractionReport,
    InvalidModelOutputError,
    attribute_code_number,
    build_website,
    clean_email,
    clean_terms,
    closest_pdf_text,
    extract,
    find_page,
    find_page_after,
    shortened_quote,
)
from app.extraction.llm_client import Completion
from app.extraction.schemas import Header, ollama_schema

# The agreed output shape (from #138). Our output must have the same keys.
STRUCTURE_FILE = (
    Path(__file__).resolve().parents[1] / "helper" / "outline-text-structure.json"
)


# =============================================================================
# Test data: a tiny fake outline and the replies a well-behaved model would give
# =============================================================================

# Already split into pages, like read_pdf_pages returns.
# Written so each test below has a known page to find.
FAKE_PAGES = [
    (
        1,
        "COMPSCI 2CO3 Data Structures\n"
        "Fall 2026\n"
        "Website Avenue to Learn\n"
        "(https://avenue.mcmaster.ca).\n"
        "Instructor Jelle Hellings (jh@mcmaster.ca).\n"
        "Lectures Tuesday: 3:30PM–4:20PM (ITB 137).",  # – is an en dash
    ),
    (
        2,
        "Assignment 1 (10%) due 2026-09-25.\n"
        "Final exam (50%).\n"
        "Use of GenAI tools is prohibited in this class.",
    ),
    (
        3,
        "Learning outcomes\nAnalyzing correctness of algorithms.",
    ),
]

HEADER_REPLY = {
    "term": ["Fall 2026"],
    "course_code": "COMPSCI 2CO3",
    "course_title": "Data Structures",
    "website": {
        "link": "https://avenue.mcmaster.ca",
        # On page 1 this quote is split over two lines.
        "source_text": "Website Avenue to Learn (https://avenue.mcmaster.ca).",
    },
    "contact": [
        {
            "instructor": "Jelle Hellings",
            "email": "jh@mcmaster.ca",
            "source_text": "Instructor Jelle Hellings (jh@mcmaster.ca).",
            # Empty quote = no office hours line; must become null in the output.
            "office_hours": {"source_text": ""},
        }
    ],
}

SECTIONS_REPLY = {
    "sections": [
        {
            "section": "C01",
            "lectures": [
                {
                    "has_location": True,
                    # Plain hyphen here, en dash in the PDF: must still be found.
                    "source_text": "Tuesday: 3:30PM-4:20PM (ITB 137).",
                }
            ],
            "tutorials": [],
            "teaching_assistants": [],
        }
    ]
}

ASSESSMENTS_REPLY = {
    "assessments": [
        {
            "name": "Assignment 1",
            "type": "assignment",
            "source_text": "Assignment 1 (10%) due 2026-09-25.",
            "date": "2026-09-25",
            "weight_percent": 10,
        },
        {
            "name": "Final exam",
            "type": "final_exam",
            "source_text": "Final exam (50%).",
            # Not YYYY-MM-DD: the extractor must drop it and warn.
            "date": "Dec 2026",
            "weight_percent": 50,
        },
    ]
}

MATERIALS_POLICIES_REPLY = {
    "materials": {"has_materials": False, "source_text": ""},
    "genai": {
        "has_genai": True,
        "source_text": "Use of GenAI tools is prohibited in this class.",
    },
    "advisory": {"has_advisory": False, "source_text": ""},
    "discrimination": {
        "has_discrimination": True,
        # Invented quote: it is not in the PDF, so it must be flagged.
        "source_text": "We value an inclusive classroom.",
    },
}

OUTCOMES_REPLY = {
    "learning_outcomes": [{"text": "Analyzing correctness of algorithms."}],
    "graduate_attributes": [],
}

# One reply per step, keyed by the step's name.
GOOD_REPLIES = {
    "header": HEADER_REPLY,
    "sections": SECTIONS_REPLY,
    "assessments": ASSESSMENTS_REPLY,
    "materials_policies": MATERIALS_POLICIES_REPLY,
    "outcomes": OUTCOMES_REPLY,
}


# =============================================================================
# A fake model
# =============================================================================


class FakeModel:
    """Stands in for llm_client.complete and records how it was called.

    Args:
        replies: the reply to give for each step name.
        steps_that_loop_first: steps whose first attempt imitates the original
            bug (whitespace until the token limit); the retry then succeeds.
    """

    def __init__(self, replies=None, steps_that_loop_first=()):
        self.replies = replies or GOOD_REPLIES
        self.steps_that_loop_first = set(steps_that_loop_first)

        # Every call as (step name, temperature), in order.
        self.calls = []

        # Whether thinking was turned on, per step name.
        self.think_by_step = {}

        # Each step sends its own task prompt, so the prompt tells us the step.
        self.step_name_by_prompt = {step.task_prompt: step.name for step in STEPS}

    def __call__(
        self,
        instructions,
        data,
        task=None,
        schema=None,
        max_tokens=0,
        temperature=0.0,
        think=False,
    ):
        # The outline must arrive as data, never mixed into the instructions.
        assert "Course outline text" in data
        assert "Course outline" not in instructions

        step_name = self.step_name_by_prompt[task]
        self.calls.append((step_name, temperature))
        self.think_by_step[step_name] = think

        is_first_attempt = temperature == 0.0
        if step_name in self.steps_that_loop_first and is_first_attempt:
            return Completion(
                text="{\n\n\n\n",
                prompt_tokens=9,
                output_tokens=max_tokens,
                hit_token_limit=True,
            )

        return Completion(
            text=json.dumps(self.replies[step_name]),
            prompt_tokens=100,
            output_tokens=50,
            hit_token_limit=False,
        )


def run_extraction(model=None):
    """Extract the fake outline with a fake model (good replies by default)."""
    return extract("outline.pdf", FAKE_PAGES, call_model=model or FakeModel())


# =============================================================================
# Tests: the output
# =============================================================================


def test_output_matches_outline_structure():
    """The output has the same keys as outline-text-structure.json (for Vanessa)."""
    output = run_extraction()
    expected = json.loads(STRUCTURE_FILE.read_text(encoding="utf-8"))

    output_keys = set(output) - {"extraction_report"}
    assert output_keys == set(expected)

    assert set(output["course_information"]) == set(expected["course_information"])
    assert set(output["assessments"][0]) == set(expected["assessments"][0])
    assert set(output["policies"]) == set(expected["policies"])


def test_source_pages_are_found_by_code():
    """source_page comes from searching the PDF text, despite small differences."""
    output = run_extraction()
    course_information = output["course_information"]

    # Quote split over two lines in the PDF.
    assert course_information["website"]["source_page"] == 1

    # En dash in the PDF, plain hyphen in the quote.
    first_lecture = course_information["sections"][0]["lectures"][0]
    assert first_lecture["source_page"] == 1

    assert output["assessments"][0]["source_page"] == 2
    assert output["learning_outcomes"][0]["source_page"] == 3
    assert output["policies"]["genai"]["source_page"] == 2


def test_invented_quotes_are_flagged_not_trusted():
    """A quote that is not in the PDF gets no page and is reported."""
    output = run_extraction()

    assert output["policies"]["discrimination"]["source_page"] is None

    unverified = output["extraction_report"]["unverified_sources"]
    assert [entry["field"] for entry in unverified] == ["policies.discrimination"]

    # Empty quotes mean "not present": no page, but not reported as unverified.
    assert output["materials"]["source_page"] is None


def test_ids_and_invalid_dates():
    """Code assigns ids; a date that is not YYYY-MM-DD is dropped with a warning."""
    output = run_extraction()

    assert [item["id"] for item in output["assessments"]] == ["1", "2"]
    assert output["learning_outcomes"][0]["id"] == "LO1"

    final_exam = output["assessments"][1]
    assert final_exam["date"] is None

    warnings = output["extraction_report"]["warnings"]
    assert any("Dec 2026" in warning for warning in warnings)


# =============================================================================
# Tests: calling the model
# =============================================================================


def test_looping_reply_is_retried_once_at_higher_temperature():
    """A cut-off reply is retried once, at a higher temperature, and succeeds."""
    model = FakeModel(steps_that_loop_first=["header"])
    output = run_extraction(model)

    assert output["course_information"]["course_code"] == "COMPSCI 2CO3"

    header_temperatures = [
        temperature for step_name, temperature in model.calls if step_name == "header"
    ]
    assert header_temperatures == [0.0, 0.3]


def test_invalid_reply_twice_raises_with_raw_text():
    """Two bad replies raise an error that keeps the raw reply for debugging."""
    # Wrong type for "term" and the other keys missing.
    broken_replies = {**GOOD_REPLIES, "header": {"term": "Fall 2026"}}

    with pytest.raises(InvalidModelOutputError) as error:
        run_extraction(FakeModel(replies=broken_replies))

    assert error.value.step_name == "header"
    assert "Fall 2026" in error.value.reply_text


def test_empty_outline_is_rejected():
    """A PDF with no text (e.g. a scan) is refused before calling the model."""
    with pytest.raises(ValueError):
        extract("scan.pdf", [(1, "  ")], call_model=FakeModel())


def test_thinking_is_on_for_assessments_only():
    """Thinking is used only where it helps (assessments), as it is slow."""
    model = FakeModel()
    run_extraction(model)

    assert model.think_by_step == {
        "header": False,
        "sections": False,
        "assessments": True,
        "materials_policies": False,
        "outcomes": False,
    }


def test_ollama_schema_has_no_refs_and_requires_fields():
    """The schema sent to Ollama is self-contained; every field is required."""
    schema = ollama_schema(Header)

    assert "$ref" not in json.dumps(schema)
    assert "$defs" not in schema
    assert set(schema["required"]) == {
        "term",
        "course_code",
        "course_title",
        "website",
        "contact",
    }


# =============================================================================
# Tests: finding quotes in the PDF text
# =============================================================================


def test_find_page_handles_page_breaks_and_missing():
    """Quotes across a page break get the first page; unknown quotes get None."""
    pages = [(1, "end of one"), (2, "page two")]

    assert find_page("one page two", pages) == 1
    assert find_page("not here", pages) is None
    assert find_page("", pages) is None


def test_find_page_handles_line_break_hyphens():
    """Words hyphenated over a line break still match; real hyphens are kept."""
    pages = [
        (1, "spanning trees"),
        (2, "topological search, span-\nning trees"),
    ]

    # The model joined the word back together.
    assert find_page("search, spanning trees", pages) == 2

    # The model kept the line-break hyphen.
    assert find_page("search, span- ning trees", pages) == 2

    # A real hyphenated word at a line end must still match as written.
    assert find_page("a well-\nknown", [(1, "a well-\nknown")]) == 1


def test_glued_quote_is_shortened_to_the_part_in_the_pdf():
    """A quote glued from two places is cut to the end part that is in the PDF."""
    pages = [
        (1, "Nothing here."),
        (2, "The preliminary deadlines are as follows: September 25; October 9."),
    ]
    glued_quote = "The preliminary deadlines are as follows: October 9"

    shorter_quote, page_number = shortened_quote(glued_quote, pages)

    assert shorter_quote == "October 9"
    assert page_number == 2


def test_quote_with_no_matching_part_is_not_shortened():
    """If no end part is in the PDF either, the quote is left as it is."""
    pages = [(1, "Nothing here.")]

    shorter_quote, page_number = shortened_quote("Due: tomorrow at noon", pages)

    assert shorter_quote == "Due: tomorrow at noon"
    assert page_number is None


def test_extraction_stores_the_shortened_quote_and_warns():
    """The output keeps the quote that can be highlighted, and says it changed it."""
    glued_replies = {
        **GOOD_REPLIES,
        "assessments": {
            "assessments": [
                {
                    "name": "Assignment 1",
                    "type": "assignment",
                    # "Grading:" is not next to the date in the fake PDF.
                    "source_text": "Grading: Assignment 1 (10%) due 2026-09-25.",
                    "date": "2026-09-25",
                    "weight_percent": 10,
                }
            ]
        },
    }

    output = run_extraction(FakeModel(replies=glued_replies))
    assignment = output["assessments"][0]

    assert assignment["source_text"] == "Assignment 1 (10%) due 2026-09-25."
    assert assignment["source_page"] == 2

    report = output["extraction_report"]
    assert report["unverified_sources"] == [
        {
            "field": "policies.discrimination",
            "source_text": "We value an inclusive classroom.",
        }
    ]
    assert any("quote shortened" in warning for warning in report["warnings"])


def test_find_page_matches_whole_words_only():
    """ "December 1" must not match "December 10" on an earlier page."""
    pages = [
        (1, "Lectures run until December 10, 2026."),
        (4, "Deadlines: November 24; and December 1."),
    ]

    assert find_page("December 1", pages) == 4


def test_missing_office_hours_become_null():
    """An empty office hours quote from the model is written as null."""
    output = run_extraction()

    contact = output["course_information"]["contact"][0]
    assert contact["office_hours"] is None


def test_identical_office_hours_lines_get_each_instructors_page():
    """Same office hours line twice: each instructor gets the one after their name."""
    pages = [
        (
            1,
            "Instructor Jelle Hellings (jh@mcmaster.ca).\n"
            "Office hours See Avenue to Learn for updates.\n"
            "Instructor Vincent Maccio (macciov@mcmaster.ca).",
        ),
        (2, "Office hours See Avenue to Learn for updates."),
    ]
    office_hours_line = "Office hours See Avenue to Learn for updates."

    hellings_page = find_page_after(
        office_hours_line, "Instructor Jelle Hellings (jh@mcmaster.ca).", pages
    )
    maccio_page = find_page_after(
        office_hours_line, "Instructor Vincent Maccio (macciov@mcmaster.ca).", pages
    )

    assert hellings_page == 1
    assert maccio_page == 2


def test_find_page_handles_hyphen_kept_without_line_break():
    """The model copied "limita-tions" from a PDF line break "limita-" / "tions"."""
    pages = [(4, "identifies their limita-\ntions, and selects")]

    assert find_page("identifies their limita-tions, and selects", pages) == 4


def test_attribute_codes_keep_only_the_number():
    """Labels copied into the code are removed; plain codes are kept."""
    assert attribute_code_number("Graduate Attribute Indicator 1.4") == "1.4"
    assert attribute_code_number("Graduate Attribute 1") == "1"
    assert attribute_code_number("1.1") == "1.1"
    assert attribute_code_number("KB") == "KB"


def test_emails_are_cleaned():
    """Stray characters from the PDF are removed from email addresses."""
    assert clean_email("mishrs23@mcmaster.ca}") == "mishrs23@mcmaster.ca"
    assert clean_email("(jh@mcmaster.ca,") == "jh@mcmaster.ca"
    assert clean_email("no address here") is None
    assert clean_email(None) is None


def test_reworded_text_is_replaced_with_the_exact_pdf_text():
    """Slightly reworded text is swapped for the real PDF sentence."""
    pages = [
        (2, "Learning outcomes\n▶Analyzing the correctness of algorithms."),
    ]

    # The model dropped "the".
    closest = closest_pdf_text("Analyzing correctness of algorithms.", pages)

    assert closest == ("Analyzing the correctness of algorithms.", 2)


def test_unrelated_text_is_not_replaced():
    """Text that is not close to anything in the PDF stays flagged instead."""
    pages = [(1, "Learning outcomes\nAnalyzing correctness of algorithms.")]

    assert closest_pdf_text("Students will enjoy the weekly labs.", pages) is None


def test_extraction_never_stores_reworded_outcomes():
    """A reworded outcome in the model's reply is stored as the PDF wrote it."""
    reworded = {
        **GOOD_REPLIES,
        "outcomes": {
            "learning_outcomes": [{"text": "Analyzing the correctness of algorithms."}],
            "graduate_attributes": [],
        },
    }

    output = run_extraction(FakeModel(replies=reworded))
    outcome = output["learning_outcomes"][0]

    assert outcome["text"] == "Analyzing correctness of algorithms."
    assert outcome["source_page"] == 3
    warnings = output["extraction_report"]["warnings"]
    assert any("reworded text" in warning for warning in warnings)


def test_full_year_terms_become_fall_and_winter():
    """ "Term 1" / "Term 2" map to the fall and the following winter."""
    pages = [(1, "SFWRENG 4G06\nAugust 27, 2026\nTerm 1 (CD-Fall)")]

    assert clean_terms(["Term 1 (CD-Fall)", "Term 2"], pages) == [
        "Fall 2026",
        "Winter 2027",
    ]
    # Normal term names are kept as they are.
    assert clean_terms(["Fall 2026"], pages) == ["Fall 2026"]


def test_website_link_must_be_a_web_address():
    """A name in the link field is replaced by the address in the quote, or dropped."""
    report = ExtractionReport()
    pages = [(1, "Website Avenue to Learn (https://avenue.mcmaster.ca).")]

    named_with_address = Header.model_validate(
        {
            **HEADER_REPLY,
            "website": {
                "link": "Avenue to Learn",
                "source_text": "Website Avenue to Learn (https://avenue.mcmaster.ca).",
            },
        }
    )
    website = build_website(named_with_address, pages, report)
    assert website["link"] == "https://avenue.mcmaster.ca"

    named_only = Header.model_validate(
        {
            **HEADER_REPLY,
            "website": {"link": "Avenue to Learn", "source_text": "Avenue to Learn"},
        }
    )
    assert build_website(named_only, pages, report) is None
