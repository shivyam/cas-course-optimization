"""Shared types for the extraction package: the page list and the report.

Kept in their own module because every other extraction module uses them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# The outline as read from the PDF: a list of (page number, page text),
# with pages numbered from 1.
Pages = list[tuple[int, str]]


@dataclass
class ExtractionReport:
    """Notes collected while one outline is extracted, saved with the output."""

    # One entry per model call: step, attempt, seconds, tokens read and written.
    model_calls: list[dict] = field(default_factory=list)

    # Quotes that could not be found in the PDF (reworded or invented).
    unverified_sources: list[dict] = field(default_factory=list)

    # Anything else worth a human look (dropped dates, cut-off outline).
    warnings: list[str] = field(default_factory=list)
