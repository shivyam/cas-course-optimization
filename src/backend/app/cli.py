"""Command-line tools for the CAS Course Optimization backend."""

import argparse
import sys
from pathlib import Path

from app.api.outlines import (
    MAX_FILE_SIZE_BYTES,
    extract_pdf_text,
    save_extracted_text,
)


def main() -> int:
    """Extract text from a local course outline PDF."""
    parser = argparse.ArgumentParser(
        description="Extract text from a course outline PDF."
    )
    parser.add_argument("pdf_path", type=Path, help="Path to the course outline PDF.")
    args = parser.parse_args()

    pdf_path = args.pdf_path
    if not pdf_path.is_file():
        print(f"Error: file not found: {pdf_path}", file=sys.stderr)
        return 1
    if pdf_path.suffix.lower() != ".pdf":
        print("Error: only PDF files are supported.", file=sys.stderr)
        return 1

    try:
        contents = pdf_path.read_bytes()
    except OSError as error:
        print(f"Error: unable to read {pdf_path}: {error}", file=sys.stderr)
        return 1

    if len(contents) > MAX_FILE_SIZE_BYTES:
        print("Error: PDF files must be 10 MB or smaller.", file=sys.stderr)
        return 1
    if not contents.startswith(b"%PDF-"):
        print("Error: the file is not a valid PDF.", file=sys.stderr)
        return 1

    try:
        text = extract_pdf_text(contents)
        output_path = save_extracted_text(pdf_path.name, text)
    except ValueError:
        print("Error: the file is not a valid PDF.", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"Error: unable to save extracted text: {error}", file=sys.stderr)
        return 1

    print("Succesfully extracted course outline text to: " + str(output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
