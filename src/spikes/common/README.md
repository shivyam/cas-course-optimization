# Shared harness for the local-model spikes

One harness for every model-selection spike, so results can be compared directly.
Ported from the #38 Gemma 4 E2B spike (`src/spikes/gemma4/spike_gemma.py` on `spike/gemma4`).
The prompts, JSON schema, `--postprocess` rules, PDF extraction and scorer are unchanged.
Parts not used for the model comparison (linking, fewshot, graduate attributes, pdfplumber)
were removed; they are still on `spike/gemma4`.

| File | What it does |
|---|---|
| `spike_llm.py` | Entry point: options, one run per outline, saves to `results/<model>/` |
| `config.py` | Ollama address, where the outline PDFs are |
| `extraction.py` | PDF to text (Shivya's PyMuPDF code) |
| `prompts.py` | Prompts, JSON schema, prompt-injection lines (same for every model) |
| `ollama_client.py` | Calls to Ollama |
| `strategies.py` | baseline and think |
| `rules.py` | `--postprocess` rules and the 100% weight check |
| `scoring.py` | Scoring against `keys/`, printed report |
| `run_spike.sh` | Wraps `spike_llm.py` with the fixed comparison settings, records the Ollama/model environment, saves a log |
| `compare_inject.py` | Prompt-injection gate: compares injected runs with normal runs (any change is a fail) |
| `keys/` | Hand-made answer keys for the five Fall 2026 test outlines (44 items) |

## Fixed settings for every model

PyMuPDF extraction (Shivya's `extract_pdf_text()`, pymupdf 1.27.2.2), `--postprocess`,
`num_ctx` 16384, temperature 0, CPU, the same five outlines and keys.

## Setup (Git Bash, once)

```bash
cd src/spikes/common
python -m venv .venv
source .venv/Scripts/activate
pip install pymupdf==1.27.2.2
cp .env.example .env    # then set SPIKE_OUTLINES_DIR
ollama pull llama3.2:3b
```

## Spike #40: Llama 3.2 3B

```bash
# Smoke test: one outline, baseline
bash src/spikes/common/run_spike.sh --model llama3.2:3b --strategies baseline --outlines 2DA4 --label smoke

# Phase A: baseline and think, all five outlines, one run
bash src/spikes/common/run_spike.sh --model llama3.2:3b --label phaseA

# Phase B: the better strategy from Phase A, three runs
bash src/spikes/common/run_spike.sh --model llama3.2:3b --strategies think --runs 3 --label phaseB

# Phase C: prompt-injection gate (run for gemma4:e2b too)
bash src/spikes/common/run_spike.sh --model llama3.2:3b --strategies think \
     --outlines "2OP3 2DA4" --inject "ignore alter disguised" --label phaseC
python src/spikes/common/compare_inject.py src/spikes/common/results/llama3.2-3b --strategy think
```

Phase C needs normal runs of the same outlines and strategy in the same results folder
(Phase A or B provides them for Llama; Gemma needs them re-run with this harness).

## Adding another model later

Pass a different `--model` (for example `qwen3:4b`). Results go to their own folder.
