# PDF highlighting PoC

Flag wrong/important text on a course outline PDF from a CLI. Highlights
accumulate on **one** working file:

`<source>_flags.pdf`

## Setup

```powershell
cd src/spikes/pdf-highlighting
..\..\backend\.venv\Scripts\Activate.ps1
```

## Run

Close any old `highlight_poc.py` session first, then:

```powershell
python highlight_poc.py --reset --open
```

View **`COMPSCI2C03-VincentMaccio_Fall2026_flags.pdf` only**.

```text
flag> Teaching Assistants
flag> TBD
flag> /path
flag> /quit
```

If the file is locked, close that PDF tab and retry — the script will not create
`_v1` / `_highlighted` copies anymore.

### Commands

| Command | Meaning |
|---|---|
| `<text>` | Highlight (accumulates, case-insensitive) |
| `/open` | Open `*_flags.pdf` |
| `/path` | Print working path |
| `/list` | Session flags |
| `/json` | Extraction `source_text` values |
| `/reset` | Clear highlights |
| `/quit` | Exit |

## Files kept in repo

- `COMPSCI2C03-VincentMaccio_Fall2026.pdf` — source outline
- `COMPSCI_2C03.json` — extraction fixture
- `highlight_poc.py`, `README.md`
