"""Finding the model's quotes in the PDF text, for traceability.

Every extracted value carries a quote (source_text). This module finds which
page each quote is on, and repairs quotes that are not in the PDF as written:
  - find_page / find_page_after: exact search, forgiving about line breaks,
    hyphens, quotes, dashes and capitals.
  - shortened_quote: for quotes the model glued together from two places.
  - closest_pdf_text: for quotes the model reworded; returns the exact PDF text.

Nothing here calls the model; it is plain text matching.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

from app.extraction.report import Pages

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
# Repairing quotes that are not in the PDF as written
# =============================================================================


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
