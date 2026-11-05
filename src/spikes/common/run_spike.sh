#!/usr/bin/env bash
# Model-selection spikes: run one model on the course outlines and save everything
# printed to results/<model>/logs/<label>_<timestamp>.log
#
# Usage (Git Bash, from anywhere):
#   bash src/spikes/common/run_spike.sh --model MODEL
#        [--strategies "baseline think"]      default: "baseline think"
#        [--outlines all|hard|easy|"2OP3 2DA4"] default: all (codes pick single outlines)
#        [--runs N]                           default: 1
#        [--inject "ignore alter disguised"]  runs each variant instead of a normal run
#        [--outlines-dir PATH]
#        [--label NAME]                       used in the log file name
#
# Fixed for every run so models compare fairly: PyMuPDF text (Shivya's extraction),
# --postprocess --num-ctx 16384 --key-dir keys
#
# Spike #40 (Llama 3.2 3B):
#   Phase A: bash src/spikes/common/run_spike.sh --model llama3.2:3b --label phaseA
#   Phase B: bash src/spikes/common/run_spike.sh --model llama3.2:3b --strategies think --runs 3 --label phaseB
#   Phase C: bash src/spikes/common/run_spike.sh --model llama3.2:3b --strategies think \
#              --outlines "2OP3 2DA4" --inject "ignore alter disguised" --label phaseC
#            python src/spikes/common/compare_inject.py src/spikes/common/results/llama3.2-3b
#
# Outline PDFs are not in the repo: use --outlines-dir, SPIKE_OUTLINES_DIR, or a .env file
# in this folder (copy .env.example to .env). The folder must contain Fall_2026/.
# Each outline takes about 4 to 7 minutes per strategy on CPU. Ollama must be running.

# Work from this script's folder so keys/, results/ and spike_llm.py are found
cd "$(dirname "$0")" || exit 1

# ---------------------------------------------------------------------------
# Options and their defaults
# ---------------------------------------------------------------------------
MODEL=""
STRATEGIES="baseline think"
OUTLINE_SET="all"
RUNS=1
INJECT=""
LABEL="run"
OUTLINES_DIR_ARG=()   # empty unless --outlines-dir is given
while [ $# -gt 0 ]; do
  case "$1" in
    --model)        MODEL="$2"; shift 2 ;;
    --strategies)   STRATEGIES="$2"; shift 2 ;;
    --outlines)     OUTLINE_SET="$2"; shift 2 ;;
    --runs)         RUNS="$2"; shift 2 ;;
    --inject)       INJECT="$2"; shift 2 ;;
    --label)        LABEL="$2"; shift 2 ;;
    --outlines-dir) OUTLINES_DIR_ARG=(--outlines-dir "$2"); shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done
# No default model on purpose: every result must say which model produced it
if [ -z "$MODEL" ]; then
  echo "ERROR: --model is required, for example --model llama3.2:3b"; exit 1
fi

# ---------------------------------------------------------------------------
# Which outlines to run
# hard = dates only in a schedule or table (failed most often in #38)
# easy = dates next to each item in the grading scheme
# ---------------------------------------------------------------------------
declare -A BY_CODE=(
  [2OP3]="Fall_2026/SFWRENG2OP3_AngelaZavaleta_Fall2026.pdf"
  [2XC3]="Fall_2026/SFWRENG2XC3_SamScott_Fall2026.pdf"
  [2DA4]="Fall_2026/SFWRENG2DA4_RyanLeduc_Fall2026.pdf"
  [2DM3]="Fall_2026/SFWRENG2DM3_RidhaKhedri_Fall2026.pdf"
  [2C03]="Fall_2026/COMPSCI2C03-VincentMaccio_Fall2026.pdf"
)
case "$OUTLINE_SET" in
  all)  CODES="2OP3 2XC3 2DA4 2DM3 2C03" ;;
  hard) CODES="2OP3 2XC3" ;;
  easy) CODES="2DA4 2DM3 2C03" ;;
  *)    CODES="$OUTLINE_SET" ;;
esac
# Turn the codes into PDF paths (relative to the outlines folder)
OUTLINES=()
for c in $CODES; do
  if [ -z "${BY_CODE[$c]}" ]; then echo "Unknown outline code: $c (use 2OP3 2XC3 2DA4 2DM3 2C03)"; exit 1; fi
  OUTLINES+=("${BY_CODE[$c]}")
done

# ---------------------------------------------------------------------------
# Output locations and settings shared by every run
# ---------------------------------------------------------------------------
# Folder-safe model name, same rule as model_slug() in spike_llm.py (llama3.2:3b -> llama3.2-3b)
SLUG=$(echo "$MODEL" | sed 's/[^A-Za-z0-9._-]/-/g')
OUT_DIR="results/$SLUG"
mkdir -p "$OUT_DIR/logs"
STAMP=$(date +%Y%m%d-%H%M%S)
LOG="$OUT_DIR/logs/${LABEL}_${STAMP}.log"
# These settings are fixed so every model is tested the same way. Do not change them
# for one model only, or the comparison with the other spikes is no longer fair.
COMMON_ARGS=(--model "$MODEL" --postprocess --num-ctx 16384
             --key-dir keys --runs "$RUNS" "${OUTLINES_DIR_ARG[@]}")

# Show Python output straight away (no buffering) and keep the log in UTF-8
export PYTHONUNBUFFERED=1
export PYTHONIOENCODING=utf-8

# Everything inside { ... } is shown on screen and copied to the log by tee
{
  echo "Model-selection spike run '$LABEL', started $(date)"
  echo "Model: $MODEL   Extractor: pymupdf   Strategies: $STRATEGIES   Runs: $RUNS"
  echo "Injection variants: ${INJECT:-none (normal runs)}"
  echo "Outlines: ${OUTLINES[*]}"
  echo

  # -------------------------------------------------------------------------
  # Checks before starting, so a long run does not fail halfway
  # -------------------------------------------------------------------------
  # Use a venv in this folder, else the gemma4 spike's venv, else system Python
  if [ -f .venv/Scripts/activate ]; then source .venv/Scripts/activate
  elif [ -f .venv/bin/activate ]; then source .venv/bin/activate
  elif [ -f ../gemma4/.venv/Scripts/activate ]; then source ../gemma4/.venv/Scripts/activate
  else echo "WARNING: no .venv found; using the system Python"
  fi
  echo "Python: $(command -v python)"

  # The PDF library must be installed
  if ! python -c "import pymupdf" 2>/dev/null; then
    echo "ERROR: pymupdf is not installed. Run: pip install pymupdf==1.27.2.2"; exit 1
  fi

  # Every outline PDF must be found. The first argument is the --outlines-dir path
  # if one was given; the rest are the outline paths.
  if ! python - "${OUTLINES_DIR_ARG[@]:1}" "${OUTLINES[@]}" <<'PY'
import sys
from config import outlines_dir, resolve_pdf, OUTLINES_ENV
args = sys.argv[1:]
cli = args.pop(0) if args and not args[0].lower().endswith(".pdf") else None
base, source = outlines_dir(cli)
print(f"Outlines folder: {base}  [{source}]")
missing = [a for a in args if resolve_pdf(a, base) is None]
for a in missing:
    print(f"ERROR: not found: {a}")
if missing:
    print(f"Set {OUTLINES_ENV} in .env (copy .env.example), set the environment variable, "
          "or pass --outlines-dir PATH.")
    sys.exit(1)
print(f"All {len(args)} outline PDFs found.")
PY
  then exit 1; fi

  # Ollama must be running, and the model must already be pulled
  if ! curl -s --max-time 5 http://localhost:11434/api/tags > /dev/null; then
    echo "ERROR: Ollama is not reachable at http://localhost:11434. Start Ollama and run this again."; exit 1
  fi
  if ! curl -s http://localhost:11434/api/tags | grep -q "\"name\":\"$MODEL\""; then
    echo "ERROR: $MODEL is not pulled. Run: ollama pull $MODEL"; exit 1
  fi

  # Record the exact environment so results can be compared later:
  # Ollama version, model digest (which exact download), size, quantization and
  # trained context length, plus the machine. Saved next to the results.
  ENV_FILE="$OUT_DIR/env_${LABEL}_${STAMP}.json"
  python - "$MODEL" "$ENV_FILE" <<'PY'
import json, platform, sys, urllib.request
model, path = sys.argv[1], sys.argv[2]
def get(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())
version = get("http://localhost:11434/api/version").get("version")
tags = {m["name"]: m for m in get("http://localhost:11434/api/tags")["models"]}
show = get("http://localhost:11434/api/show", {"model": model})
info = {
    "ollama_version": version,
    "model": model,
    "digest": tags.get(model, {}).get("digest"),
    "size_bytes": tags.get(model, {}).get("size"),
    "details": show.get("details"),
    "context_length": next((v for k, v in (show.get("model_info") or {}).items()
                            if k.endswith(".context_length")), None),
    "machine": platform.platform(),
    "processor": platform.processor(),
}
open(path, "w", encoding="utf-8").write(json.dumps(info, indent=2))
d = info["details"] or {}
print(f"Ollama {version}; {model} digest {str(info['digest'])[:12]}, "
      f"{d.get('parameter_size')} params, {d.get('quantization_level')}, "
      f"trained context {info['context_length']}")
print(f"Environment saved to {path}")
PY
  echo

  # -------------------------------------------------------------------------
  # The runs: every strategy, and for each one every injection variant
  # ("none" means a normal run without injection)
  # -------------------------------------------------------------------------
  for strategy in $STRATEGIES; do
    for variant in ${INJECT:-none}; do
      INJ_ARGS=()   # no --inject for a normal run
      [ "$variant" != "none" ] && INJ_ARGS=(--inject "$variant")
      echo "=================================================================="
      echo "STRATEGY: $strategy   INJECTION: $variant   started $(date +%H:%M:%S)"
      echo "=================================================================="
      start=$(date +%s)
      if python spike_llm.py "${OUTLINES[@]}" --strategy "$strategy" "${COMMON_ARGS[@]}" "${INJ_ARGS[@]}"; then
        status="finished"
      else
        # Keep going so one failure does not lose the rest of a long run
        status="FAILED (exit code $?), continuing"
      fi
      echo "STRATEGY: $strategy INJECTION: $variant $status in about $(( ($(date +%s) - start) / 60 )) min"
      echo
    done
  done

  echo "All done $(date)"
  echo "Scores per run are in $OUT_DIR/summary.csv"
  # While this runs, open Task Manager > Performance > Memory and note the peak for the write-up.
} 2>&1 | tee "$LOG"

echo
echo "Log saved to: src/spikes/common/$LOG"
