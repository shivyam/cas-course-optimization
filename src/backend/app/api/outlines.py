"""Course outline upload endpoint."""

import os
import re
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Annotated
from xml.etree import ElementTree

import pymupdf
from fastapi import APIRouter, File, HTTPException, UploadFile

router = APIRouter(tags=["outlines"])

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
MAX_BATCH_FILES = 50
DEFAULT_EXTRACTED_TEXT_DIR = (
    Path(__file__).resolve().parents[4] / "data" / "extracted_text"
)
EXTRACTED_TEXT_DIR = Path(
    os.getenv("EXTRACTED_TEXT_DIR", str(DEFAULT_EXTRACTED_TEXT_DIR))
)
EXTRACTED_TEXT_REPO_PATH = Path("data") / "extracted_text"
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/x-pdf",
    "text/x-tex",
    "application/x-tex",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/octet-stream",
}
ALLOWED_EXTENSIONS = {".pdf", ".tex", ".docx"}


def extract_latex_text(contents: bytes) -> str:
    """Extract readable text from a UTF-8 LaTeX source file."""
    try:
        source = contents.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("The uploaded LaTeX file is not valid UTF-8 text.") from error

    # Remove comments while preserving line structure, then turn common
    # formatting commands into their braced content before removing the rest.
    source = re.sub(r"(?<!\\)%[^\n]*", "", source)
    source = re.sub(
        r"\\(?:section|subsection|subsubsection|paragraph|textbf|textit|emph|underline|texttt|text|title|author|date)\*?\{([^{}]*)\}",
        r"\1",
        source,
    )
    source = re.sub(r"\\href\{[^{}]*\}\{([^{}]*)\}", r"\1", source)
    source = re.sub(r"\\(?:begin|end)\{[^{}]*\}", "", source)
    source = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^]]*\])?", "", source)
    source = re.sub(r"(?<!\\)[{}]", "", source)
    source = source.replace("\\\\", "\n")
    source = re.sub(r"\\([%{}_$#&])", r"\1", source)
    source = source.replace("~", " ")
    return re.sub(r"\n{3,}", "\n\n", source).strip()


def extract_docx_text(contents: bytes) -> str:
    """Extract paragraphs and table rows from a modern Word document."""
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    try:
        with zipfile.ZipFile(BytesIO(contents)) as archive:
            xml = archive.read("word/document.xml")
        root = ElementTree.fromstring(xml)
    except (KeyError, ElementTree.ParseError, zipfile.BadZipFile) as error:
        raise ValueError("The uploaded file is not a valid Word document.") from error

    blocks: list[str] = []
    body = root.find(f"{namespace}body")
    if body is None:
        return ""
    for block in body:
        if block.tag == f"{namespace}p":
            text = "".join(node.text or "" for node in block.iter(f"{namespace}t"))
            if text.strip():
                blocks.append(text.strip())
        elif block.tag == f"{namespace}tbl":
            for row in block.findall(f"{namespace}tr"):
                cells = []
                for cell in row.findall(f"{namespace}tc"):
                    cell_text = "".join(
                        node.text or "" for node in cell.iter(f"{namespace}t")
                    ).strip()
                    cells.append(cell_text)
                if any(cells):
                    blocks.append("\t".join(cells))
    return "\n\n".join(blocks)


def extract_pdf_text(contents: bytes) -> str:
    """Extract text from a PDF's contents."""
    try:
        document = pymupdf.open(stream=contents, filetype="pdf")
        text = "\n\n".join(page.get_text() for page in document).strip()
    except pymupdf.FileDataError as error:
        raise ValueError("The uploaded file is not a valid PDF.") from error
    finally:
        if "document" in locals():
            document.close()
    return text


def save_extracted_text(filename: str, text: str) -> str:
    """Save extracted text and return its repo-relative path with POSIX separators."""
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename).stem).strip("._")
    safe_stem = safe_stem or "outline"
    output_path = EXTRACTED_TEXT_DIR / f"{safe_stem}.txt"

    EXTRACTED_TEXT_DIR.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")

    # Use POSIX separators so API responses stay stable across Windows and Unix.
    return (EXTRACTED_TEXT_REPO_PATH / output_path.name).as_posix()


async def process_outline_upload(file: UploadFile) -> dict:
    """Validate one course outline and return extracted text metadata."""
    # Check both the browser-provided type and the filename before reading the
    # upload so unsupported files fail with a clear client-facing response.
    filename = file.filename or ""
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Only PDF, LaTeX (.tex), and Word (.docx) files are supported.",
        )
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail="The uploaded file type is not supported.")

    # Read one byte beyond the limit so an oversized upload can be detected
    # without loading an unbounded request body into memory.
    contents = await file.read(MAX_FILE_SIZE_BYTES + 1)
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="Files must be 10 MB or smaller.")

    try:
        if extension == ".pdf":
            if not contents.startswith(b"%PDF-"):
                raise ValueError("The uploaded file is not a valid PDF.")
            text = extract_pdf_text(contents)
            text_extraction = "pymupdf"
        elif extension == ".tex":
            text = extract_latex_text(contents)
            text_extraction = "latex"
        else:
            text = extract_docx_text(contents)
            text_extraction = "docx"
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    try:
        text_file = save_extracted_text(filename, text)
    except OSError as error:
        raise HTTPException(
            status_code=500, detail="Unable to save extracted outline text."
        ) from error

    return {
        "filename": filename,
        "status": "received",
        "size_bytes": len(contents),
        "text_extraction": text_extraction,
        "text": text,
        "text_file": str(text_file),
    }


async def process_outline_upload_result(file: UploadFile) -> dict:
    """Process one upload and return a success or failure result object."""
    filename = file.filename or "unknown.pdf"
    try:
        result = await process_outline_upload(file)
        return {**result, "ok": True}
    except HTTPException as error:
        detail = error.detail
        if not isinstance(detail, str):
            detail = "The course outline could not be uploaded."
        return {
            "ok": False,
            "filename": filename,
            "status": "error",
            "detail": detail,
            "status_code": error.status_code,
        }


@router.post("/outlines")
async def upload_outline(file: Annotated[UploadFile, File()]) -> dict:
    """Validate a course outline and return upload metadata."""
    return await process_outline_upload(file)


@router.post("/outlines/batch")
async def upload_outlines(
    files: Annotated[
        list[UploadFile],
        File(description="One or more PDF, LaTeX, or Word outlines"),
    ],
) -> dict:
    """Validate and extract text from many course outlines at once."""
    if not files:
        raise HTTPException(status_code=400, detail="Select at least one outline file.")
    if len(files) > MAX_BATCH_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Upload at most {MAX_BATCH_FILES} outline files at once.",
        )

    results = [await process_outline_upload_result(file) for file in files]
    succeeded = sum(1 for result in results if result.get("ok"))
    failed = len(results) - succeeded

    return {
        "status": "completed",
        "total": len(results),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }
