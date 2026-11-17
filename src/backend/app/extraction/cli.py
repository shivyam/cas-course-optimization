"""Command-line tool: extract one course outline PDF to JSON with the local LLM.

Usage (from src/backend, with Ollama running and the model pulled):
    cas-llm-extract path/to/outline.pdf
    python -m app.extraction.cli path/to/outline.pdf --out-dir somewhere/

To use the CAS GPU server, start scripts/gpu_ollama.sh first and prefix the
command with OLLAMA_URL=http://localhost:11435.

Writes <out-dir>/<outline name>_<date-time>.json, pretty-printed. Every run gets
its own file, so a new run never overwrites an earlier one. If the model's reply
is invalid, the raw reply is written to <outline name>_<date-time>.<step>.raw.txt
instead so it can be inspected.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

# Reuse Shivya's PDF checks and reading, so the CLI and the upload endpoint
# accept exactly the same files.
from app.api.outlines import MAX_FILE_SIZE_BYTES, read_pdf_pages
from app.extraction import llm_client
from app.extraction.extractor import InvalidModelOutputError, extract

# Same repo-level data/ folder the text extraction uses; it is git-ignored, so
# extracted outline data is never committed by accident.
# parents[4]: cli.py -> extraction -> app -> backend -> src -> repo root.
DEFAULT_OUTPUT_FOLDER = Path(__file__).resolve().parents[4] / "data" / "extracted_json"


def print_error(message: str) -> None:
    """Print an error message to stderr, where error output belongs."""
    print(f"Error: {message}", file=sys.stderr)


def output_file_name(pdf_name: str) -> str:
    """File name (without extension) for this run's output.

    Example: "COMPSCI2C03_JelleHellings_Fall 2026.pdf"
          -> "COMPSCI2C03_JelleHellings_Fall_2026_20261117-143005"
    """
    # Replace anything that is not a letter, digit, ".", "_" or "-" with "_",
    # the same way the text extraction names its files.
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(pdf_name).stem)
    safe_name = safe_name.strip("._") or "outline"

    # The date and time of this run, so repeated runs of the same outline are
    # all kept side by side instead of overwriting each other.
    run_time = datetime.now().strftime("%Y%m%d-%H%M%S")

    return f"{safe_name}_{run_time}"


def read_pdf(pdf_path: Path) -> bytes | None:
    """Return the PDF's bytes, or None (after printing why) if it is not usable."""
    if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
        print_error(f"not a PDF file: {pdf_path}")
        return None

    pdf_bytes = pdf_path.read_bytes()

    # Same size limit as the upload endpoint.
    if len(pdf_bytes) > MAX_FILE_SIZE_BYTES:
        print_error("the PDF is larger than 10 MB.")
        return None

    # Every real PDF starts with "%PDF-".
    if not pdf_bytes.startswith(b"%PDF-"):
        print_error("the file is not a valid PDF.")
        return None

    return pdf_bytes


def print_summary(output: dict, output_file: Path) -> None:
    """Print a short summary, so problems are visible without opening the file."""
    report = output["extraction_report"]

    print(f"Done in {report['seconds']}s -> {output_file}")
    print(f"  {len(output['assessments'])} assessments")
    print(f"  {len(output['learning_outcomes'])} learning outcomes")
    print(f"  {len(report['unverified_sources'])} quotes not found in the PDF")

    for warning in report["warnings"]:
        print(f"  warning: {warning}")


def main(argv: list[str] | None = None) -> int:
    """Run the CLI. Returns the exit code: 0 on success, 1 on any error."""
    parser = argparse.ArgumentParser(
        description="Extract a course outline PDF to JSON."
    )
    parser.add_argument("pdf_path", type=Path, help="Path to the course outline PDF.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUTPUT_FOLDER)
    args = parser.parse_args(argv)

    # 1. Check the file before doing any slow work.
    pdf_bytes = read_pdf(args.pdf_path)
    if pdf_bytes is None:
        return 1

    # 2. Check the model is reachable, with a hint on how to fix it if not.
    model_name = llm_client.settings().model_name
    if not llm_client.is_available():
        print_error(
            f"Ollama is not running or {model_name} is not pulled "
            f"(try: ollama pull {model_name})."
        )
        return 1

    # 3. Run the extraction.
    output_folder = args.out_dir
    output_folder.mkdir(parents=True, exist_ok=True)
    file_name = output_file_name(args.pdf_path.name)

    print(f"Extracting {args.pdf_path.name} with {model_name} ...")
    try:
        output = extract(args.pdf_path.name, read_pdf_pages(pdf_bytes))

    except InvalidModelOutputError as error:
        # Keep the bad reply so we can see what the model actually wrote.
        reply_file = output_folder / f"{file_name}.{error.step_name}.raw.txt"
        reply_file.write_text(error.reply_text, encoding="utf-8")
        print_error(f"{error}\nThe model's reply was saved to {reply_file}")
        return 1

    except (
        ValueError,  # unreadable PDF, or no text in it
        llm_client.ModelUnavailableError,
        llm_client.ModelTimeoutError,
    ) as error:
        print_error(str(error))
        return 1

    # 4. Save pretty-printed JSON. ensure_ascii=False writes characters such as
    #    an en dash as themselves instead of as "–" escape codes.
    output_file = output_folder / f"{file_name}.json"
    output_json = json.dumps(output, indent=2, ensure_ascii=False)
    output_file.write_text(output_json + "\n", encoding="utf-8")

    # 5. Tell the user how it went.
    print_summary(output, output_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
