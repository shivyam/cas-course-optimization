"""PDF text extraction: Shivya's PyMuPDF code, the extractor every model is tested with.

(The spike's own pdfplumber extractor was dropped after #38 showed PyMuPDF keeps
table cells in order; it is still on branch spike/gemma4.)
"""

from __future__ import annotations

import sys
from pathlib import Path


def extract_pdf_text(pdf_path: Path) -> str:
    """Shivya's extraction, copied unchanged from extract_pdf_text() in
    src/backend/app/api/outlines.py on branch feat/pdf-outline-upload (commit 91f35b2).
    Uses the same PyMuPDF version: pip install pymupdf==1.27.2.2
    """
    try:
        import pymupdf
    except ImportError:
        sys.exit("pymupdf is not installed. Run: pip install pymupdf==1.27.2.2")
    contents = pdf_path.read_bytes()
    try:
        document = pymupdf.open(stream=contents, filetype="pdf")
        text = "\n\n".join(page.get_text() for page in document).strip()
    except pymupdf.FileDataError as error:
        raise ValueError("The uploaded file is not a valid PDF.") from error
    finally:
        if "document" in locals():
            document.close()
    return text
