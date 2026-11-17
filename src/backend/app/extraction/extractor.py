"""Extraction module: turns page-by-page outline text into the outline JSON structure.

How it works:
  1. The outline is split into five small steps (header, sections, assessments,
     materials and policies, outcomes). Each step is one model call with its own
     JSON Schema and a tight token limit, so a small model stays on task and a
     runaway reply fails fast instead of filling the whole context.
  2. Each reply is checked against its schema. An invalid or cut-off reply is
     retried once at a slightly higher temperature; if it fails again the step
     raises InvalidModelOutputError with the raw reply kept for debugging.
  3. Code, not the model, fills in `source_page` by finding each `source_text`
     in the page text. A quote that cannot be found is given `source_page: null`
     and listed in `extraction_report.unverified_sources`, because the
     highlighting step cannot show it and it may have been invented.
  4. Code also fills in ids, the filename, and drops dates that are not YYYY-MM-DD.

The result has the same shape as `src/backend/helper/outline-text-structure.json`,
plus one `extraction_report` key with model, timing and warnings.

Reading order: `extract()` at the bottom is the entry point. Above it are the
helpers it uses, grouped as: finding quotes, calling the model, building output.
"""

from __future__ import annotations

import re
import time
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from difflib import SequenceMatcher

from pydantic import BaseModel, ValidationError

from app.extraction import llm_client, prompts
from app.extraction.schemas import (
    Assessments,
    Header,
    MaterialsAndPolicies,
    Outcomes,
    Sections,
    ollama_schema,
)

# The outline as read from the PDF: a list of (page number, page text),
# with pages numbered from 1.
Pages = list[tuple[int, str]]

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


# =============================================================================
# The five extraction steps
# =============================================================================


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


@dataclass
class ExtractionReport:
    """Notes collected while one outline is extracted, saved with the output."""

    # One entry per model call: step, attempt, seconds, tokens read and written.
    model_calls: list[dict] = field(default_factory=list)

    # Quotes that could not be found in the PDF (reworded or invented).
    unverified_sources: list[dict] = field(default_factory=list)

    # Anything else worth a human look (dropped dates, cut-off outline).
    warnings: list[str] = field(default_factory=list)


# =============================================================================
# Finding quotes in the page text
# =============================================================================

# PDF text often differs from what the model copies in small ways: curly
# quotes, dashes, invisible characters. These are mapped to plain versions
# before comparing. (Ligatures such as "fi" are handled by NFKC below.)
CHARACTERS_TO_SIMPLIFY = str.maketrans(
    {
        "‘": "'",  # left single quote
        "’": "'",  # right single quote / apostrophe
        "“": '"',  # left double quote
        "”": '"',  # right double quote
        "–": "-",  # en dash (e.g. "3:30PM–4:20PM")
        "—": "-",  # em dash
        "−": "-",  # minus sign
        " ": " ",  # non-breaking space
        "­": "",  # soft hyphen (invisible, PDFs use it for line breaks)
    }
)

# A word split over a line break: a letter, "-", optional spaces, a newline,
# then a letter on the next line. Example: "span-\nning".
HYPHEN_AT_LINE_END = re.compile(r"(\w)-[ \t]*\n\s*(\w)")


def simplify_for_search(text: str) -> str:
    """Return `text` lower-cased, with quotes, dashes and whitespace unified.

    Applied to both the quote and the page, so line breaks, double spaces and
    capitalisation differences do not stop a quote from being found.
    """
    # NFKC turns compatibility characters into plain ones (e.g. "ﬁ" -> "fi").
    text = unicodedata.normalize("NFKC", text)
    text = text.translate(CHARACTERS_TO_SIMPLIFY)

    # Any run of spaces, tabs or newlines becomes one space.
    text = re.sub(r"\s+", " ", text)

    return text.strip().casefold()


def join_hyphenated_words(text: str) -> str:
    """Join words the PDF split over a line break: "span-\\nning" -> "spanning"."""
    return HYPHEN_AT_LINE_END.sub(r"\1\2", text)


def remove_hyphens_in_words(text: str) -> str:
    """Remove hyphens between two letters: "limita-tions" -> "limitations".

    Hyphens next to digits or spaces stay ("3:30pm-4:20pm", "a - b").
    """
    return re.sub(r"(?<=[a-z])-(?=[a-z])", "", text)


def contains_quote(page_text: str, quote: str) -> bool:
    """True if `quote` appears in `page_text` as whole words.

    A plain "in" check is not enough: "December 1" is inside "December 10",
    which put a December 1 deadline on the wrong page. So the quote must not be
    directly preceded or followed by a letter or digit.
    """
    # (?<!\w) = no letter/digit just before; (?!\w) = none just after.
    # re.escape makes characters like "(" or "." in the quote match literally.
    whole_words = r"(?<!\w)" + re.escape(quote) + r"(?!\w)"
    return re.search(whole_words, page_text) is not None


def find_page_after(quote: str, earlier_quote: str, pages: Pages) -> int | None:
    """Return the page of the first `quote` that comes after `earlier_quote`.

    Used when the same line appears more than once. Example: both instructors
    in Hellings 2CO3 have "Office hours See Avenue to Learn for updates.", so
    each instructor's office hours are looked for after their own name line.
    Falls back to find_page if `earlier_quote` cannot be found.
    """
    wanted = simplify_for_search(quote)
    anchor = simplify_for_search(earlier_quote)

    # Join all pages into one text, remembering where each page starts.
    page_starts = []
    all_text = ""
    for page_number, page_text in pages:
        page_starts.append((len(all_text), page_number))
        all_text += simplify_for_search(page_text) + " "

    anchor_match = re.search(re.escape(anchor), all_text) if anchor else None
    if not wanted or anchor_match is None:
        return find_page(quote, pages)

    # Look for the quote only after the end of the earlier quote.
    whole_words = re.compile(r"(?<!\w)" + re.escape(wanted) + r"(?!\w)")
    quote_match = whole_words.search(all_text, anchor_match.end())
    if quote_match is None:
        return find_page(quote, pages)

    # The match is on the last page that starts at or before it.
    found_page = None
    for start_position, page_number in page_starts:
        if start_position <= quote_match.start():
            found_page = page_number
    return found_page


def find_page(quote: str, pages: Pages) -> int | None:
    """Return the number of the first page that contains `quote`, or None.

    A word split over a line break ("limita-" / "tions") can be copied by the
    model in three ways, so each page is searched in three spellings:
      1. as it is:               "limita- tions" (the line break became a space)
      2. line breaks joined:     "limitations"
      3. no hyphens in words:    "limitations", compared with the quote's
                                 hyphens removed too, so "limita-tions" matches.
    Spelling 3 also keeps real hyphens working ("well-known" vs "wellknown"
    on both sides), but is tried last because it is the loosest.
    """
    wanted = simplify_for_search(quote)

    # An empty quote means "not present"; there is nothing to find.
    if not wanted:
        return None

    wanted_without_hyphens = remove_hyphens_in_words(wanted)

    # Prepare every page once. For each page, a list of
    # (page text in one spelling, the quote in the matching spelling).
    searchable_pages = []
    for page_number, page_text in pages:
        as_is = simplify_for_search(page_text)
        joined = simplify_for_search(join_hyphenated_words(page_text))
        spellings = [
            (as_is, wanted),
            (joined, wanted),
            (remove_hyphens_in_words(joined), wanted_without_hyphens),
        ]
        searchable_pages.append((page_number, spellings))

    # Usual case: the quote is on one page.
    for page_number, spellings in searchable_pages:
        for page_version, quote_version in spellings:
            if contains_quote(page_version, quote_version):
                return page_number

    # Rare case: the quote runs over a page break. Glue each page to the next
    # one and search again. The page where the quote starts is reported.
    for index in range(len(searchable_pages) - 1):
        page_number, this_page_spellings = searchable_pages[index]
        _, next_page_spellings = searchable_pages[index + 1]

        for (this_page, quote_version), (next_page, _) in zip(
            this_page_spellings, next_page_spellings, strict=True
        ):
            if contains_quote(f"{this_page} {next_page}", quote_version):
                return page_number

    return None


# =============================================================================
# Calling the model
# =============================================================================


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


# =============================================================================
# Building the output
# =============================================================================


def with_source_page(
    item: dict,
    pages: Pages,
    report: ExtractionReport,
    field_name: str,
    quote_key: str = "source_text",
    search_after: str | None = None,
) -> dict:
    """Return a copy of `item` with a `source_page` added, found from its quote.

    `field_name` (e.g. "assessments[2]") says which value this is, for the report.
    `quote_key` is the field holding the quote; learning outcomes use "text".
    `search_after`, if given, is a quote that must come before this one in the
    outline (see find_page_after).
    """
    quote = item.get(quote_key) or ""
    if search_after:
        page_number = find_page_after(quote, search_after, pages)
    else:
        page_number = find_page(quote, pages)

    # Not found as written: the model may have glued words from different
    # places together. Try the end of the quote instead (see shortened_quote).
    if quote and page_number is None:
        shorter_quote, page_number = shortened_quote(quote, pages)

        if page_number is not None:
            report.warnings.append(
                f"{field_name}: quote shortened from {quote!r} to "
                f"{shorter_quote!r} to match the PDF"
            )
            # Store the shorter quote, so the highlighting step can find it.
            item = {**item, quote_key: shorter_quote}

    # Still not found: the model probably reworded it. Text is never allowed
    # to be reworded, so swap in the exact PDF text if a close match exists.
    if quote and page_number is None:
        closest = closest_pdf_text(quote, pages)

        if closest is not None:
            pdf_text, page_number = closest
            report.warnings.append(
                f"{field_name}: reworded text {quote!r} replaced with the exact "
                f"PDF text {pdf_text!r}"
            )
            item = {**item, quote_key: pdf_text}

    # A non-empty quote that is still not in the PDF was reworded or invented.
    # Empty quotes mean "not present" and are expected to have no page.
    if quote and page_number is None:
        report.unverified_sources.append({"field": field_name, "source_text": quote})

    return {**item, "source_page": page_number}


# How similar (0 to 1) a PDF line or sentence must be to a reworded quote to
# replace it. 0.85 allows small rewording ("the course" vs "this course") but
# not a different sentence. Below this, the quote stays flagged as unverified.
CLOSE_ENOUGH = 0.85

# Bullet characters some outlines put at the start of list lines ("▶Analyzing").
BULLETS = "▶•▪●*-"


def candidate_passages(page_text: str) -> list[str]:
    """Lines and sentences of a page that a quote could have been copied from.

    Includes single lines, two lines joined (a sentence wrapped over a line
    break), and full sentences, each with whitespace tidied and bullets removed.
    """
    text = join_hyphenated_words(page_text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    candidates = list(lines)

    # Two lines joined, for sentences that wrap onto the next line.
    for index in range(len(lines) - 1):
        candidates.append(f"{lines[index]} {lines[index + 1]}")

    # Whole sentences, which can span several lines.
    flat_text = re.sub(r"\s+", " ", text)
    candidates.extend(re.split(r"(?<=[.!?])\s+", flat_text))

    tidy = []
    for candidate in candidates:
        candidate = re.sub(r"\s+", " ", candidate).strip().lstrip(BULLETS).strip()
        if candidate:
            tidy.append(candidate)
    return tidy


def closest_pdf_text(quote: str, pages: Pages) -> tuple[str, int] | None:
    """The PDF line or sentence most like `quote`, if it is close enough.

    Returns (the exact PDF text, its page), or None if nothing reaches
    CLOSE_ENOUGH. Used to undo small rewording by the model, so that only text
    really in the outline is ever stored.
    """
    wanted = simplify_for_search(quote)
    best_score = 0.0
    best_match = None

    for page_number, page_text in pages:
        for candidate in candidate_passages(page_text):
            score = SequenceMatcher(
                None, simplify_for_search(candidate), wanted
            ).ratio()
            if score > best_score:
                best_score = score
                best_match = (candidate, page_number)

    if best_score < CLOSE_ENOUGH:
        return None
    return best_match


# Where a quote may be cut: after a ":" or ";" followed by a space.
QUOTE_CUT_POINT = re.compile(r"[:;]\s+")

# Shorter than this, a piece of a quote could match almost anywhere.
MIN_SHORTENED_QUOTE_LENGTH = 5


def shortened_quote(quote: str, pages: Pages) -> tuple[str, int | None]:
    """Find the longest end part of `quote` that is in the PDF.

    Example: the outline says "The preliminary deadlines are as follows:
    September 25; October 9; ...", and the model quotes "The preliminary
    deadlines are as follows: October 9". That is not in the PDF as one piece,
    but its end, "October 9", is.

    Returns (the shorter quote, its page), or (quote, None) if no end part is
    found. End parts are tried from longest to shortest, so as much of the
    model's quote as possible is kept.
    """
    for cut_point in QUOTE_CUT_POINT.finditer(quote):
        end_part = quote[cut_point.end() :].strip()

        if len(end_part) < MIN_SHORTENED_QUOTE_LENGTH:
            continue

        page_number = find_page(end_part, pages)
        if page_number is not None:
            return end_part, page_number

    return quote, None


def checked_date(value: str | None, report: ExtractionReport, field_name: str):
    """Return `value` if it is a real YYYY-MM-DD date, otherwise None.

    Better no date than a wrong one: the schedule checks rely on it.
    """
    if value is None:
        return None

    try:
        # Rejects "Dec 2026", "2026-13-01", "TBA" and so on.
        return date.fromisoformat(value).isoformat()
    except ValueError:
        report.warnings.append(f"{field_name}: dropped date {value!r} (not YYYY-MM-DD)")
        return None


# An email address: name@domain.part, e.g. "mishrs23@mcmaster.ca".
EMAIL_ADDRESS = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def clean_email(email: str | None) -> str | None:
    """Keep only the email address itself.

    PDF text can carry stray characters next to an address, e.g. Mishra 3VA3
    gave "mishrs23@mcmaster.ca}". If no address is found, None is returned.
    """
    if not email:
        return None
    match = EMAIL_ADDRESS.search(email)
    if match is None:
        return None
    return match.group()


def build_contacts(header: Header, pages: Pages, report: ExtractionReport) -> list:
    """Instructors, each with the page of their name line and office hours line."""
    contacts = []

    for index, contact in enumerate(header.contact):
        field_name = f"contact[{index}]"

        # The instructor line, without office hours (handled just below).
        entry = with_source_page(
            contact.model_dump(exclude={"office_hours"}), pages, report, field_name
        )
        entry["email"] = clean_email(contact.email)

        # Office hours are a separate line, so they get their own page.
        # An empty quote means the outline has none: null in the output.
        if not contact.office_hours.source_text.strip():
            entry["office_hours"] = None
        else:
            # Office hours come after the instructor's name line, so search
            # from there. Otherwise two instructors with the same line ("See
            # Avenue to Learn") would both get the first one's page.
            entry["office_hours"] = with_source_page(
                contact.office_hours.model_dump(),
                pages,
                report,
                f"{field_name}.office_hours",
                search_after=entry["source_text"],
            )

        contacts.append(entry)

    return contacts


def build_sections(sections: Sections, pages: Pages, report: ExtractionReport) -> list:
    """Lecture sections, with a page for every lecture, tutorial and TA line."""
    section_list = []

    for section_index, section in enumerate(sections.sections):
        section_entry = {"section": section.section}

        # The three lists are handled the same way.
        for list_name in ("lectures", "tutorials", "teaching_assistants"):
            items_with_pages = []

            for item_index, item in enumerate(getattr(section, list_name)):
                field_name = f"sections[{section_index}].{list_name}[{item_index}]"
                items_with_pages.append(
                    with_source_page(item.model_dump(), pages, report, field_name)
                )

            section_entry[list_name] = items_with_pages

        section_list.append(section_entry)

    return section_list


def build_assessments(
    assessments: Assessments, pages: Pages, report: ExtractionReport
) -> list:
    """Assessments with ids "1", "2", ... (as in the reference files) and pages."""
    assessment_list = []

    for index, assessment in enumerate(assessments.assessments):
        field_name = f"assessments[{index}]"

        entry = {"id": str(index + 1), **assessment.model_dump()}
        entry["date"] = checked_date(assessment.date, report, field_name)

        assessment_list.append(with_source_page(entry, pages, report, field_name))

    return assessment_list


def build_learning_outcomes(
    outcomes: Outcomes, pages: Pages, report: ExtractionReport
) -> list:
    """Learning outcomes with ids "LO1", "LO2", ...; the text itself is the quote."""
    outcome_list = []

    for index, outcome in enumerate(outcomes.learning_outcomes):
        entry = {"id": f"LO{index + 1}", **outcome.model_dump()}
        outcome_list.append(
            with_source_page(
                entry, pages, report, f"learning_outcomes[{index}]", quote_key="text"
            )
        )

    return outcome_list


def build_graduate_attributes(
    outcomes: Outcomes, pages: Pages, report: ExtractionReport
) -> list:
    """Graduate attributes, each with its page and a clean code."""
    attribute_list = []

    for index, attribute in enumerate(outcomes.graduate_attributes):
        entry = attribute.model_dump()
        entry["code"] = attribute_code_number(attribute.code)

        attribute_list.append(
            with_source_page(entry, pages, report, f"graduate_attributes[{index}]")
        )

    return attribute_list


# An attribute code: a number, optionally with ".number" parts ("1", "1.4").
ATTRIBUTE_CODE = re.compile(r"\d+(?:\.\d+)*")


def attribute_code_number(code: str) -> str:
    """Keep only the number of a graduate attribute code.

    The model sometimes copies the label as well:
        "Graduate Attribute Indicator 1.4" -> "1.4"
        "Graduate Attribute 1"             -> "1"
        "1.1"                              -> "1.1"
    If there is no number at all, the code is kept as the model wrote it.
    """
    match = ATTRIBUTE_CODE.search(code)
    if match is None:
        return code
    return match.group()


def build_policies(
    materials_and_policies: MaterialsAndPolicies,
    pages: Pages,
    report: ExtractionReport,
) -> dict:
    """The three policies (GenAI, advisory, discrimination), each with its page."""
    policies = {}

    for policy_name in ("genai", "advisory", "discrimination"):
        policy = getattr(materials_and_policies, policy_name)
        policies[policy_name] = with_source_page(
            policy.model_dump(), pages, report, f"policies.{policy_name}"
        )

    return policies


# A full-year course numbers its terms. Team rule: term 1 is the fall and
# term 2 the following winter.
TERM_NUMBER = re.compile(r"^\s*term\s*([12])(?!\d)", re.IGNORECASE)

# A year such as 2026.
YEAR = re.compile(r"(?<!\d)20\d\d(?!\d)")


def clean_terms(terms: list[str], pages: Pages) -> list[str]:
    """Turn "Term 1" / "Term 2" into "Fall <year>" / "Winter <next year>".

    Smith 4G06 only writes "Term 1 (CD-Fall)" and "Term 2 (CD-Winter)", and
    the model copies that even when told to map it. Other terms ("Fall 2026")
    are kept as they are. The year is the first year written in the outline
    (e.g. its date, "August 27, 2026"); without one, the terms are kept.
    """
    outline_text = " ".join(page_text for _, page_text in pages)
    year_match = YEAR.search(outline_text)
    if year_match is None:
        return terms
    fall_year = int(year_match.group())

    cleaned = []
    for term in terms:
        term_number = TERM_NUMBER.match(term)
        if term_number is None:
            cleaned.append(term)
        elif term_number.group(1) == "1":
            cleaned.append(f"Fall {fall_year}")
        else:
            cleaned.append(f"Winter {fall_year + 1}")
    return cleaned


# A web address: starts with http(s):// or www., up to the next space.
WEB_ADDRESS = re.compile(r"(?:https?://|www\.)[^\s)>\]]+")


def build_website(header: Header, pages: Pages, report: ExtractionReport):
    """The course website, only if it has a real web address.

    The model sometimes puts a name ("Avenue to Learn") in the link field. Then
    the address is taken from the quoted line if it has one; otherwise there is
    no usable link and the website is left out (null).
    """
    if header.website is None:
        return None

    website = header.website.model_dump()

    if WEB_ADDRESS.search(website["link"]) is None:
        address_in_quote = WEB_ADDRESS.search(website["source_text"])
        if address_in_quote is None:
            report.warnings.append(
                f"website: {website['link']!r} is not a web address; left out"
            )
            return None
        # Drop a full stop or comma that ends the sentence after the address.
        website["link"] = address_in_quote.group().rstrip(".,;")

    return with_source_page(website, pages, report, "website")


def build_output(
    filename: str, replies: dict, pages: Pages, report: ExtractionReport
) -> dict:
    """Assemble the outline JSON from the five checked replies.

    Adds what the model is never asked for: ids, source pages, the filename.
    The key order follows outline-text-structure.json.
    """
    header: Header = replies["header"]
    sections: Sections = replies["sections"]
    assessments: Assessments = replies["assessments"]
    materials_and_policies: MaterialsAndPolicies = replies["materials_policies"]
    outcomes: Outcomes = replies["outcomes"]

    website = build_website(header, pages, report)

    course_information = {
        "term": clean_terms(header.term, pages),
        "course_code": header.course_code,
        "course_title": header.course_title,
        "website": website,
        "contact": build_contacts(header, pages, report),
        "sections": build_sections(sections, pages, report),
    }

    materials = with_source_page(
        materials_and_policies.materials.model_dump(), pages, report, "materials"
    )

    return {
        "course_outline_filename": filename,
        "course_information": course_information,
        "assessments": build_assessments(assessments, pages, report),
        "materials": materials,
        "learning_outcomes": build_learning_outcomes(outcomes, pages, report),
        "graduate_attributes": build_graduate_attributes(outcomes, pages, report),
        "policies": build_policies(materials_and_policies, pages, report),
    }


# =============================================================================
# Entry point
# =============================================================================


def extract(filename: str, pages: Pages, call_model: ModelCall | None = None) -> dict:
    """Extract one outline into the outline JSON structure.

    Args:
        filename: the PDF's file name, stored in the output.
        pages: (page number, text) pairs, from read_pdf_pages.
        call_model: defaults to the real LLM client; tests pass a fake.

    Raises:
        ValueError: the PDF has no text (e.g. a scanned document).
        ModelUnavailableError, ModelTimeoutError: from the LLM client.
        InvalidModelOutputError: a step's reply was unusable twice.
    """
    if call_model is None:
        call_model = llm_client.complete

    report = ExtractionReport()

    # The model reads the whole outline at once; the pages are only needed
    # later, to find where each quote came from.
    outline_text = "\n\n".join(page_text for _, page_text in pages).strip()

    # A scanned PDF has images, not text, so PyMuPDF returns nothing.
    if not outline_text:
        raise ValueError("The outline has no extractable text (is it a scanned PDF?).")

    # Run the five steps in order. Any failure stops the whole extraction.
    replies = {}
    for step in STEPS:
        replies[step.name] = run_step(step, outline_text, call_model, report)

    output = build_output(filename, replies, pages, report)

    # Ollama silently drops the start of a prompt that does not fit in the
    # context window. If the model read (almost) a full window, warn about it.
    config = llm_client.settings()
    model_name = config.model_name
    context_size = config.context_size
    most_tokens_read = max(call["prompt_tokens"] or 0 for call in report.model_calls)
    if most_tokens_read >= context_size - 64:
        report.warnings.append(
            f"The model read {most_tokens_read} tokens with a {context_size}-token "
            "context: the outline was probably cut off. Raise LLM_NUM_CTX."
        )

    # Extra key (not in outline-text-structure.json) for debugging and review.
    total_seconds = sum(call["seconds"] for call in report.model_calls)
    output["extraction_report"] = {
        "model": model_name,
        "seconds": round(total_seconds, 2),
        "steps": report.model_calls,
        "unverified_sources": report.unverified_sources,
        "warnings": report.warnings,
    }

    return output
