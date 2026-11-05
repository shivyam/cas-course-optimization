"""Settings shared by the spike modules: Ollama address and where the outline PDFs live."""

from __future__ import annotations

import re
from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/chat"

# ---------------------------------------------------------------------------
# Where the outline PDFs live
#
# The PDFs are not in the repo. Point the script at your local copy, in this order
# of priority:
#   1. --outlines-dir PATH on the command line
#   2. the SPIKE_OUTLINES_DIR environment variable
#   3. SPIKE_OUTLINES_DIR=PATH in a .env file in this folder (copy .env.example)
#   4. the outlines/ folder in this folder
# PDF arguments can then be given relative to that folder,
# e.g. "Fall_2026/SFWRENG2OP3_AngelaZavaleta_Fall2026.pdf".
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
OUTLINES_ENV = "SPIKE_OUTLINES_DIR"


def read_dotenv(path: Path) -> dict:
    """Minimal KEY=VALUE reader (no extra dependency). Ignores blank lines and comments."""
    values = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def outlines_dir(cli_value: str | None = None) -> tuple[Path, str]:
    """Return the outlines folder and where the setting came from."""
    import os

    if cli_value:
        return Path(cli_value).expanduser(), "--outlines-dir"
    if os.environ.get(OUTLINES_ENV):
        return Path(os.environ[OUTLINES_ENV]).expanduser(), f"{OUTLINES_ENV} environment variable"
    dotenv = read_dotenv(SCRIPT_DIR / ".env")
    if dotenv.get(OUTLINES_ENV):
        return Path(dotenv[OUTLINES_ENV]).expanduser(), f"{OUTLINES_ENV} in .env"
    return SCRIPT_DIR / "outlines", "default (outlines/ next to the script)"


def resolve_pdf(arg: str, base: Path) -> Path | None:
    """Find a PDF given as a path, or relative to the outlines folder."""
    # Also accept PDFs placed directly in the folder (without a Fall_2026/ subfolder)
    candidates = [Path(arg), base / arg, base / Path(arg).name]
    # Old commands used "outlines/<...>"; let those still work against the new folder
    parts = Path(arg).parts
    if parts and parts[0] == "outlines":
        candidates.append(base.joinpath(*parts[1:]))
    for c in candidates:
        if c.is_file():
            return c
    return None


def model_slug(model: str) -> str:
    """Folder-safe model name: llama3.2:3b -> llama3.2-3b."""
    return re.sub(r"[^A-Za-z0-9._-]", "-", model)
