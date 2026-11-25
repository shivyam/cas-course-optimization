"""
PoC: interactively flag/highlight wrong or important text on a course-outline PDF.

Always writes to one working file: <source>_flags.pdf
Highlights accumulate across many CLI inputs.

Examples:
  python highlight_poc.py --open
  python highlight_poc.py --reset --open -t "TBD" -t "September 25"
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF

SPIKE_DIR = Path(__file__).resolve().parent
DEFAULT_PDF = SPIKE_DIR / "COMPSCI2C03-VincentMaccio_Fall2026.pdf"
DEFAULT_JSON = SPIKE_DIR / "COMPSCI_2C03.json"


def collect_source_texts(node: object, out: list[str]) -> None:
    if isinstance(node, dict):
        value = node.get("source_text")
        if isinstance(value, str) and value.strip():
            out.append(value.strip())
        for child in node.values():
            collect_source_texts(child, out)
    elif isinstance(node, list):
        for child in node:
            collect_source_texts(child, out)


def flags_path_for(pdf_path: Path) -> Path:
    return pdf_path.with_name(f"{pdf_path.stem}_flags{pdf_path.suffix}")


def open_pdf(path: Path) -> None:
    path = path.resolve()
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        os.system(f'open "{path}"')
    else:
        os.system(f'xdg-open "{path}"')


def print_json_texts(json_path: Path) -> None:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    texts: list[str] = []
    collect_source_texts(data, texts)
    seen: set[str] = set()
    for i, text in enumerate(texts, start=1):
        if text in seen:
            continue
        seen.add(text)
        print(f"{i:3}. {text}")


def print_help() -> None:
    print(
        """
Commands:
  <text>     Highlight that text (accumulates on *_flags.pdf)
  /open      Open/reopen *_flags.pdf
  /list      Texts flagged this session
  /json      List source_text values from the extraction JSON
  /path      Show working PDF path
  /reset     Restart from the original PDF (clears highlights)
  /help      Show this help
  /quit      Save and exit
""".strip()
    )


@dataclass
class HighlightSession:
    source_pdf: Path
    working_pdf: Path
    doc: fitz.Document
    page_number: int | None = None
    auto_open: bool = False
    flagged: list[str] = field(default_factory=list)

    @classmethod
    def start(
        cls,
        source_pdf: Path,
        working_pdf: Path,
        *,
        reset: bool,
        page_number: int | None,
        auto_open: bool,
    ) -> HighlightSession:
        working_pdf.parent.mkdir(parents=True, exist_ok=True)
        if reset or not working_pdf.is_file():
            shutil.copy2(source_pdf, working_pdf)
        return cls(
            source_pdf=source_pdf,
            working_pdf=working_pdf,
            doc=fitz.open(working_pdf),
            page_number=page_number,
            auto_open=auto_open,
        )

    def close(self) -> None:
        self.doc.close()

    def _export_to_working_file(self) -> None:
        """Write the in-memory PDF to *_flags.pdf, retrying if the file is locked."""
        tmp = self.working_pdf.with_suffix(".exporting.pdf")
        self.doc.save(tmp, garbage=4, deflate=True)

        last_error: Exception | None = None
        for attempt in range(1, 6):
            try:
                os.replace(tmp, self.working_pdf)
                return
            except OSError as exc:
                last_error = exc
                print(
                    f"{self.working_pdf.name} is locked "
                    f"(close that PDF tab/viewer). Retry {attempt}/5..."
                )
                time.sleep(1.2)

        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise OSError(
            f"Could not write {self.working_pdf}. Close any open tabs for that file "
            f"and try again. Last error: {last_error}"
        )

    def save(self) -> Path:
        # Prefer incremental update of the open file.
        try:
            self.doc.saveIncr()
            return self.working_pdf.resolve()
        except Exception:
            pass

        # Fallback: export + reopen the same *_flags.pdf (never create _v1 copies).
        self._export_to_working_file()
        self.doc.close()
        self.doc = fitz.open(self.working_pdf)
        return self.working_pdf.resolve()

    def highlight(self, query: str) -> int:
        query = query.strip()
        if not query:
            print("Empty text — nothing to highlight.")
            return 0

        pages = (
            [self.doc[self.page_number - 1]]
            if self.page_number is not None
            else list(self.doc)
        )
        matches = 0
        for page in pages:
            for rect in page.search_for(query, quads=False, flags=1):
                annot = page.add_highlight_annot(rect)
                annot.set_info(content=f"Flagged: {query}")
                annot.update()
                matches += 1

        if matches == 0:
            print(f'No matches for: "{query}"')
            print("Tip: copy text from the PDF, or use /json for source_text values.")
            return 0

        saved = self.save()
        self.flagged.append(query)
        print(f'Highlighted {matches} match(es) for: "{query}"')
        print(f"Saved: {saved}")
        print("Reload *_flags.pdf in your viewer if it does not refresh automatically.")
        return matches

    def reset(self) -> None:
        self.doc.close()
        shutil.copy2(self.source_pdf, self.working_pdf)
        self.doc = fitz.open(self.working_pdf)
        self.flagged.clear()
        print(f"Reset: {self.working_pdf.resolve()}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PoC: accumulate many PDF highlights on a single *_flags.pdf file."
    )
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("-t", "--text", action="append", default=[])
    parser.add_argument("--page", type=int)
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Working PDF (default: <source>_flags.pdf)",
    )
    parser.add_argument("--open", action="store_true")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--list-json", action="store_true")
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.list_json:
        print_json_texts(args.json)
        return 0

    source_pdf = args.pdf
    if not source_pdf.is_file():
        print(f"PDF not found: {source_pdf}", file=sys.stderr)
        return 1

    working_pdf = args.output or flags_path_for(source_pdf)
    session = HighlightSession.start(
        source_pdf,
        working_pdf,
        reset=args.reset,
        page_number=args.page,
        auto_open=args.open,
    )

    print(f"Source:  {source_pdf.resolve()}")
    print(f"Working: {session.working_pdf.resolve()}")
    print("Only this working file is updated. Type /help for commands.")

    if args.open:
        try:
            open_pdf(session.working_pdf)
            print(f"Opened {session.working_pdf.name}")
        except OSError as exc:
            print(f"Could not open PDF viewer: {exc}", file=sys.stderr)

    try:
        for query in args.text:
            if query.strip():
                session.highlight(query)

        if args.once:
            return 0

        print_help()
        while True:
            try:
                raw = input("flag> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                break

            if not raw:
                continue

            command = raw.lower()
            if command in {"/quit", "/exit", "quit", "exit"}:
                break
            if command in {"/help", "help", "?"}:
                print_help()
                continue
            if command == "/open":
                session.save()
                try:
                    open_pdf(session.working_pdf)
                    print(f"Opened {session.working_pdf.resolve()}")
                except OSError as exc:
                    print(f"Could not open PDF viewer: {exc}", file=sys.stderr)
                continue
            if command == "/list":
                if not session.flagged:
                    print("No texts flagged this session yet.")
                else:
                    for i, text in enumerate(session.flagged, start=1):
                        print(f"{i:3}. {text}")
                continue
            if command == "/json":
                print_json_texts(args.json)
                continue
            if command == "/path":
                print(session.working_pdf.resolve())
                continue
            if command == "/reset":
                session.reset()
                if session.auto_open:
                    try:
                        open_pdf(session.working_pdf)
                    except OSError:
                        pass
                continue

            try:
                session.highlight(raw)
            except OSError as exc:
                print(exc, file=sys.stderr)
    finally:
        try:
            session.save()
        except Exception:
            pass
        session.close()

    print(f"Done. Highlighted PDF: {session.working_pdf.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
