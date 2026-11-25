"""Command-line tools for the CAS Course Optimization backend."""

import argparse
import sys
from pathlib import Path

from app.api.outlines import (
    MAX_FILE_SIZE_BYTES,
    ALLOWED_EXTENSIONS,
    extract_docx_text,
    extract_latex_text,
    extract_pdf_text,
    save_extracted_text,
)


def main() -> int:
    """Extract text from a local course outline file."""
    parser = argparse.ArgumentParser(
        description="Extract text from a PDF, LaTeX, or Word course outline."
    )
    parser.add_argument("outline_path", type=Path, help="Path to the course outline.")
    args = parser.parse_args()

    outline_path = args.outline_path
    if not outline_path.is_file():
        print(f"Error: file not found: {outline_path}", file=sys.stderr)
        return 1
    extension = outline_path.suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        print("Error: only PDF, LaTeX, and Word files are supported.", file=sys.stderr)
        return 1

    try:
        contents = outline_path.read_bytes()
    except OSError as error:
        print(f"Error: unable to read {outline_path}: {error}", file=sys.stderr)
        return 1

    if len(contents) > MAX_FILE_SIZE_BYTES:
        print("Error: files must be 10 MB or smaller.", file=sys.stderr)
        return 1

    try:
        if extension == ".pdf":
            if not contents.startswith(b"%PDF-"):
                raise ValueError
            text = extract_pdf_text(contents)
        elif extension == ".tex":
            text = extract_latex_text(contents)
        else:
            text = extract_docx_text(contents)
        output_path = save_extracted_text(outline_path.name, text)
    except ValueError as error:
        print(f"Error: {error or 'the file is not valid.'}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"Error: unable to save extracted text: {error}", file=sys.stderr)
        return 1

    print("Succesfully extracted course outline text to: " + str(output_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
