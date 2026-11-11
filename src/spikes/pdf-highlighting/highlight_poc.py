"""
PoC: highlight user-specified text in a course-outline PDF (PyMuPDF).

Examples:
  python highlight_poc.py --text "September 25"
  python highlight_poc.py --text "Vincent Maccio" --pdf COMPSCI2C03-VincentMaccio_Fall2026.pdf
  python highlight_poc.py   # prompts for the text to flag
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import fitz  # PyMuPDF

SPIKE_DIR = Path(__file__).resolve().parent
DEFAULT_PDF = SPIKE_DIR / "COMPSCI2C03-VincentMaccio_Fall2026.pdf"
DEFAULT_JSON = SPIKE_DIR / "COMPSCI_2C03.json"


def collect_source_texts(node: object, out: list[str]) -> None:
    """Walk the extraction JSON and collect every source_text string."""
    if isinstance(node, dict):
        value = node.get("source_text")
        if isinstance(value, str) and value.strip():
            out.append(value.strip())
        for child in node.values():
            collect_source_texts(child, out)
    elif isinstance(node, list):
        for child in node:
            collect_source_texts(child, out)


def highlight_text(
    pdf_path: Path,
    query: str,
    output_path: Path,
    *,
    page_number: int | None = None,
) -> int:
    """Search for query and add highlight annotations. Returns match count."""
    if not query.strip():
        raise ValueError("Highlight text is empty.")

    doc = fitz.open(pdf_path)
    matches = 0
    pages = (
        [doc[page_number - 1]]
        if page_number is not None
        else list(doc)
    )

    for page in pages:
        for rect in page.search_for(query, quads=False):
            page.add_highlight_annot(rect)
            matches += 1

    if matches:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(output_path, garbage=4, deflate=True)
    doc.close()
    return matches


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PoC: highlight specific text in a PDF (optionally tied to extraction JSON)."
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=DEFAULT_PDF,
        help=f"Input PDF (default: {DEFAULT_PDF.name})",
    )
    parser.add_argument(
        "--text",
        "-t",
        help="Exact text to highlight. If omitted, you will be prompted.",
    )
    parser.add_argument(
        "--page",
        type=int,
        help="1-based page number to search (default: all pages).",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Highlighted PDF path (default: <pdf>_highlighted.pdf next to the input).",
    )
    parser.add_argument(
        "--list-json",
        action="store_true",
        help=f"Print source_text values from {DEFAULT_JSON.name} and exit.",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=DEFAULT_JSON,
        help="Extraction JSON used by --list-json.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.list_json:
        data = json.loads(args.json.read_text(encoding="utf-8"))
        texts: list[str] = []
        collect_source_texts(data, texts)
        # Preserve order, drop duplicates
        seen: set[str] = set()
        for i, text in enumerate(texts, start=1):
            if text in seen:
                continue
            seen.add(text)
            print(f"{i:3}. {text}")
        return 0

    pdf_path: Path = args.pdf
    if not pdf_path.is_file():
        print(f"PDF not found: {pdf_path}", file=sys.stderr)
        return 1

    query = args.text
    if query is None:
        print("Enter the text to flag/highlight in the PDF:")
        query = input("> ").strip()
    if not query:
        print("No text provided.", file=sys.stderr)
        return 1

    output_path = args.output or pdf_path.with_name(
        f"{pdf_path.stem}_highlighted{pdf_path.suffix}"
    )

    try:
        matches = highlight_text(
            pdf_path, query, output_path, page_number=args.page
        )
    except Exception as exc:  # noqa: BLE001 — spike script surface errors plainly
        print(f"Highlight failed: {exc}", file=sys.stderr)
        return 1

    if matches == 0:
        print(f'No matches for: "{query}"')
        print("Tip: copy text exactly as it appears in the PDF (dashes/spacing matter).")
        print("     Or run with --list-json to see source_text strings from the JSON.")
        return 2

    print(f'Highlighted {matches} match(es) for: "{query}"')
    print(f"Wrote: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
