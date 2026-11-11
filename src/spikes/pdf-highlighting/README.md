# PDF highlighting PoC

Proof of concept: given a course-outline PDF (and optional extraction JSON), type the text you want to flag and write a new PDF with native highlight annotations via **PyMuPDF** (`fitz`).

## Setup

Use the backend venv (already has PyMuPDF) or a local one:

```powershell
cd src/spikes/pdf-highlighting
# option A: backend env
..\..\backend\.venv\Scripts\Activate.ps1

# option B: local env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install pymupdf==1.27.2.2
```

## Run

Prompt for the text to highlight:

```powershell
python highlight_poc.py
```

Or pass it on the command line:

```powershell
python highlight_poc.py --text "September 25"
python highlight_poc.py -t "Vincent Maccio" --page 1
```

List `source_text` values from the extraction JSON (handy copy/paste targets):

```powershell
python highlight_poc.py --list-json
```

Output defaults to `COMPSCI2C03-VincentMaccio_Fall2026_highlighted.pdf` in this folder.
