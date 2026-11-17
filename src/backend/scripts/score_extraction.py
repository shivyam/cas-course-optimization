"""Score LLM extraction output against the hand-made reference JSON files.

For every reference file in src/backend/helper/ (the answer keys from #138 and
#162), this finds the newest extraction output for the same outline in
data/extracted_json/ and compares them field by field.

Usage (from src/backend):
    .venv/Scripts/python scripts/score_extraction.py

    # other folders:
    .venv/Scripts/python scripts/score_extraction.py --outputs path/ --references path/

Not part of the test suite: it needs real model output, which CI does not have.

What counts as a match (kept simple and forgiving on purpose):
  - Text is compared after lower-casing and squashing spaces and punctuation,
    so "COMPSCI 2CO3" and "compsci2co3" are equal.
  - Assessments are paired by name first, then by (date, weight).
  - A page of 0 in a reference file means "no page", the same as null.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# src/backend/scripts/score_extraction.py -> parents[1] is src/backend,
# parents[3] is the repository root.
BACKEND_FOLDER = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]

DEFAULT_REFERENCES = BACKEND_FOLDER / "helper"
DEFAULT_OUTPUTS = REPO_ROOT / "data" / "extracted_json"

# The structure template lives in the same folder but is not an answer key.
NOT_A_REFERENCE = "outline-text-structure.json"


# =============================================================================
# Small helpers
# =============================================================================


def squash(text) -> str:
    """Lower-case and keep only letters and digits, for forgiving comparisons."""
    return re.sub(r"[^a-z0-9]", "", str(text or "").lower())


def same_page(got, expected) -> bool:
    """True if two page numbers agree. 0 and None both mean "no page"."""
    return (got or None) == (expected or None)


def load_json(path: Path) -> dict:
    """Read a JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


class Score:
    """Counts "right out of total" for one thing being checked."""

    def __init__(self):
        self.right = 0
        self.total = 0

    def add(self, is_right: bool) -> None:
        """Record one check."""
        self.total += 1
        if is_right:
            self.right += 1

    def __str__(self) -> str:
        if self.total == 0:
            return "-"
        return f"{self.right}/{self.total}"


# =============================================================================
# Pairing outputs with references
# =============================================================================


def instructor_key(reference_file: Path) -> str:
    """The instructor part of a reference file name, e.g. "jellehellings".

    File names differ slightly between the PDFs and the reference files
    ("2C03" vs "2CO3", "Fall 2026" vs "Fall2026"), but the instructor's name
    is written the same way in both, so it is used to pair them.
    """
    name_parts = re.split(r"[_\-\s]+", reference_file.stem)
    # The instructor part is the one without digits (not the course code
    # "COMPSCI2CO3" and not the term "Fall2026").
    for part in name_parts:
        if part and not any(character.isdigit() for character in part):
            return squash(part)
    return squash(reference_file.stem)


def newest_output_for(reference_file: Path, outputs_folder: Path) -> Path | None:
    """The most recently written output file for the same outline, if any."""
    key = instructor_key(reference_file)
    matching_outputs = [
        output_file
        for output_file in outputs_folder.glob("*.json")
        if key in squash(output_file.stem)
    ]
    if not matching_outputs:
        return None
    return max(matching_outputs, key=lambda output_file: output_file.stat().st_mtime)


# =============================================================================
# Comparing one output with its reference
# =============================================================================


def score_header(got: dict, expected: dict, scores: dict) -> None:
    """Term, course code, title, website and instructors."""
    got_info = got["course_information"]
    expected_info = expected["course_information"]

    for field_name in ("course_code", "course_title"):
        scores["header"].add(
            squash(got_info[field_name]) == squash(expected_info[field_name])
        )

    got_terms = {squash(term) for term in got_info["term"]}
    expected_terms = {squash(term) for term in expected_info["term"]}
    scores["header"].add(got_terms == expected_terms)

    got_link = squash((got_info["website"] or {}).get("link"))
    expected_link = squash((expected_info["website"] or {}).get("link"))
    scores["header"].add(got_link == expected_link)

    # Instructors: paired by name, then email and office hours checked.
    # Names must match as the outline writes them, titles included ("Dr.").
    got_contacts = {squash(c["instructor"]): c for c in got_info["contact"]}
    for expected_contact in expected_info["contact"]:
        got_contact = got_contacts.get(squash(expected_contact["instructor"]))
        scores["instructors"].add(got_contact is not None)
        if got_contact is None:
            continue

        scores["instructors"].add(
            squash(got_contact["email"]) == squash(expected_contact["email"])
        )

        expected_hours = expected_contact.get("office_hours") or {}
        got_hours = got_contact.get("office_hours") or {}
        if expected_hours.get("source_text"):
            scores["office hours"].add(bool(got_hours.get("source_text")))
            scores["pages"].add(
                same_page(
                    got_hours.get("source_page"), expected_hours.get("source_page")
                )
            )


def pair_assessments(got_list: list, expected_list: list) -> list:
    """Pair each reference assessment with an output assessment (or None).

    First by name ("Assignment 1" = "assignment 1"), then, for the rest, by
    the same date and weight. Each output item is used at most once.
    """
    # Output items not yet paired with a reference item.
    unused = list(got_list)
    pairs = []

    for expected in expected_list:
        found = None

        # 1. Same name.
        for item in unused:
            if squash(item["name"]) == squash(expected["name"]):
                found = item
                break

        # 2. Otherwise, same date and weight.
        if found is None:
            for item in unused:
                same_date = item["date"] == expected["date"]
                same_weight = item["weight_percent"] == expected["weight_percent"]
                if same_date and same_weight:
                    found = item
                    break

        if found is not None:
            unused.remove(found)
        pairs.append((expected, found))

    return pairs


def score_assessments(got: dict, expected: dict, scores: dict) -> list:
    """Found, date, weight and page for every reference assessment.

    Returns notes about mismatches, to print under the table.
    """
    notes = []

    extra_items = len(got["assessments"]) - len(expected["assessments"])
    if extra_items > 0:
        notes.append(f"{extra_items} more assessments than the reference")

    for expected_item, got_item in pair_assessments(
        got["assessments"], expected["assessments"]
    ):
        scores["assessments found"].add(got_item is not None)
        if got_item is None:
            notes.append(f"missing assessment: {expected_item['name']}")
            continue

        date_right = got_item["date"] == expected_item["date"]
        scores["dates"].add(date_right)
        if not date_right:
            notes.append(
                f"{expected_item['name']}: date {got_item['date']} "
                f"(reference {expected_item['date']})"
            )

        weight_right = got_item["weight_percent"] == expected_item["weight_percent"]
        scores["weights"].add(weight_right)
        if not weight_right:
            notes.append(
                f"{expected_item['name']}: weight {got_item['weight_percent']} "
                f"(reference {expected_item['weight_percent']})"
            )

        scores["pages"].add(
            same_page(got_item["source_page"], expected_item["source_page"])
        )

    return notes


def score_outcomes(got: dict, expected: dict, scores: dict) -> None:
    """Learning outcomes (by text) and graduate attributes (by code)."""
    got_outcomes = [squash(outcome["text"]) for outcome in got["learning_outcomes"]]

    for expected_outcome in expected["learning_outcomes"]:
        wanted = squash(expected_outcome["text"])
        # Forgiving: one text containing the other counts (e.g. a trailing
        # "(e.g., BFS and DFS ...)" kept by one side only).
        found = any(wanted in text or text in wanted for text in got_outcomes if text)
        scores["learning outcomes"].add(found)

    got_codes = {squash(attribute["code"]) for attribute in got["graduate_attributes"]}
    for expected_attribute in expected["graduate_attributes"]:
        scores["graduate attributes"].add(
            squash(expected_attribute["code"]) in got_codes
        )


def score_policies(got: dict, expected: dict, scores: dict) -> list:
    """Materials and the three policies: present or not, and the page."""
    notes = []

    checks = [("materials", got["materials"], expected["materials"])]
    for name in ("genai", "advisory", "discrimination"):
        checks.append((name, got["policies"][name], expected["policies"][name]))

    for name, got_part, expected_part in checks:
        flag = "has_materials" if name == "materials" else f"has_{name}"
        flag_right = got_part[flag] == expected_part[flag]
        scores["materials & policies"].add(flag_right)
        if not flag_right:
            notes.append(
                f"{name}: {flag}={got_part[flag]} (reference {expected_part[flag]})"
            )
        elif expected_part[flag]:
            scores["pages"].add(
                same_page(got_part["source_page"], expected_part["source_page"])
            )

    return notes


def score_outline(got: dict, expected: dict) -> tuple[dict, list]:
    """All scores for one outline, plus notes about what differed."""
    score_names = [
        "header",
        "instructors",
        "office hours",
        "assessments found",
        "dates",
        "weights",
        "learning outcomes",
        "graduate attributes",
        "materials & policies",
        "pages",
    ]
    scores = {name: Score() for name in score_names}

    score_header(got, expected, scores)
    notes = score_assessments(got, expected, scores)
    score_outcomes(got, expected, scores)
    notes += score_policies(got, expected, scores)

    report = got.get("extraction_report", {})
    notes.append(
        f"{report.get('seconds', '?')}s, "
        f"{len(report.get('unverified_sources', []))} quotes not found in the PDF"
    )
    return scores, notes


# =============================================================================
# Main
# =============================================================================


def main() -> int:
    """Score every reference outline that has an output, and print the results."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--outputs", type=Path, default=DEFAULT_OUTPUTS)
    parser.add_argument("--references", type=Path, default=DEFAULT_REFERENCES)
    args = parser.parse_args()

    reference_files = sorted(
        path for path in args.references.glob("*.json") if path.name != NOT_A_REFERENCE
    )

    totals = {}
    for reference_file in reference_files:
        output_file = newest_output_for(reference_file, args.outputs)
        print(f"\n=== {reference_file.stem}")
        if output_file is None:
            print("  no extraction output found")
            continue
        print(f"  output: {output_file.name}")

        scores, notes = score_outline(load_json(output_file), load_json(reference_file))

        for name, score in scores.items():
            print(f"  {name:<22} {score}")

            # Add to the totals over all outlines.
            total = totals.setdefault(name, Score())
            total.right += score.right
            total.total += score.total

        for note in notes:
            print(f"    - {note}")

    print("\n=== TOTAL over all outlines")
    for name, score in totals.items():
        print(f"  {name:<22} {score}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
