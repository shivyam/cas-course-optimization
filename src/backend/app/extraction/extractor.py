"""Extraction module: turns page-by-page outline text into the outline JSON structure.

This file is the entry point, extract(). The work is split over:
  - model_steps.py:    the five model calls (header, sections, assessments,
                       materials and policies, outcomes), each checked against
                       its JSON Schema and retried once if unusable.
  - output_builder.py: builds the output JSON from the replies, adding source
                       pages, ids and the filename, and cleaning known mistakes.
  - quote_search.py:   finds each quote in the PDF text (used by the builder).
  - report.py:         the shared Pages type and the ExtractionReport.

The result has the same shape as `src/backend/helper/outline-text-structure.json`,
plus one `extraction_report` key with model, timing and warnings. A quote that
cannot be found in the PDF gets `source_page: null` and is listed in
`extraction_report.unverified_sources`.
"""

from __future__ import annotations

from app.extraction import llm_client
from app.extraction.model_steps import STEPS, ModelCall, run_step
from app.extraction.output_builder import build_output
from app.extraction.report import ExtractionReport, Pages


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
