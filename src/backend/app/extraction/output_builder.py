"""Turning the model's checked replies into the outline JSON structure.

Adds everything the model is never asked for, in code: source pages (via
quote_search), ids, the filename. Also cleans values the model gets wrong in
predictable ways: dates, emails, graduate attribute codes, "Term 1"/"Term 2",
and website links that are not web addresses.

The output has the shape of src/backend/helper/outline-text-structure.json.
"""

from __future__ import annotations

import re
from datetime import date

from app.extraction.quote_search import (
    closest_pdf_text,
    find_page,
    find_page_after,
    shortened_quote,
)
from app.extraction.report import ExtractionReport, Pages
from app.extraction.schemas import (
    Assessments,
    Header,
    MaterialsAndPolicies,
    Outcomes,
    Sections,
)


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
