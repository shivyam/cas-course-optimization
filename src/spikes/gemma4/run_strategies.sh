#!/usr/bin/env bash
# Spike #38: run prompt strategies on course outlines and save everything printed to
# results/logs/<extractor>_<timestamp>.log
#
# Usage (Git Bash, from anywhere):
#   bash src/spikes/gemma4/run_strategies.sh [--extractor pdfplumber|pymupdf]
#                                             [--strategies "baseline think linking fewshot"]
#                                             [--outlines hard|all]
#
# Defaults reproduce the first strategy run:
#   --extractor pdfplumber --strategies "linking think fewshot" --outlines hard
#
# Shivya's extraction on all five outlines:
#   bash src/spikes/gemma4/run_strategies.sh --extractor pymupdf --strategies "baseline think linking" --outlines all
#
# Each outline takes about 5 to 7 minutes per strategy on CPU. Ollama must be running.

cd "$(dirname "$0")" || exit 1

EXTRACTOR="pdfplumber"
STRATEGIES="linking think fewshot"
OUTLINE_SET="hard"
while [ $# -gt 0 ]; do
  case "$1" in
    --extractor)  EXTRACTOR="$2"; shift 2 ;;
    --strategies) STRATEGIES="$2"; shift 2 ;;
    --outlines)   OUTLINE_SET="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

HARD=(
  "outlines/Fall_2026/SFWRENG2OP3_AngelaZavaleta_Fall2026.pdf"
  "outlines/Fall_2026/SFWRENG2XC3_SamScott_Fall2026.pdf"
)
EASY=(
  "outlines/Fall_2026/SFWRENG2DA4_RyanLeduc_Fall2026.pdf"
  "outlines/Fall_2026/SFWRENG2DM3_RidhaKhedri_Fall2026.pdf"
  "outlines/Fall_2026/COMPSCI2C03-VincentMaccio_Fall2026.pdf"
)
case "$OUTLINE_SET" in
  hard) OUTLINES=("${HARD[@]}") ;;
  all)  OUTLINES=("${HARD[@]}" "${EASY[@]}") ;;
  *) echo "--outlines must be hard or all"; exit 1 ;;
esac
COMMON_ARGS=(--extractor "$EXTRACTOR" --postprocess --num-ctx 16384 --key-dir keys)

mkdir -p results/logs
LOG="results/logs/${EXTRACTOR}_$(date +%Y%m%d-%H%M%S).log"

# Stream Python output straight away (no buffering) and keep it UTF-8 for the log
export PYTHONUNBUFFERED=1
export PYTHONIOENCODING=utf-8

{
  echo "Spike #38 strategy runs, started $(date)"
  echo "Extractor: $EXTRACTOR"
  echo "Strategies: $STRATEGIES"
  echo "Outlines: ${OUTLINES[*]}"
  echo "Options: ${COMMON_ARGS[*]}"
  echo

  # Use the spike venv if it exists
  if [ -f .venv/Scripts/activate ]; then
    source .venv/Scripts/activate
  elif [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
  else
    echo "WARNING: no .venv found here; using the system Python"
  fi
  echo "Python: $(command -v python)"

  # Check the extractor library is installed before spending an hour
  if [ "$EXTRACTOR" = "pymupdf" ] && ! python -c "import pymupdf" 2>/dev/null; then
    echo "ERROR: pymupdf is not installed in this venv. Run: pip install pymupdf==1.27.2.2"
    exit 1
  fi
  if [ "$EXTRACTOR" = "pdfplumber" ] && ! python -c "import pdfplumber" 2>/dev/null; then
    echo "ERROR: pdfplumber is not installed in this venv. Run: pip install pdfplumber"
    exit 1
  fi

  # Check Ollama is up
  if ! curl -s --max-time 5 http://localhost:11434/api/tags > /dev/null; then
    echo "ERROR: Ollama is not reachable at http://localhost:11434. Start Ollama and run this again."
    exit 1
  fi
  echo "Ollama is reachable."

  for strategy in $STRATEGIES; do
    echo
    echo "=================================================================="
    echo "STRATEGY: $strategy    started $(date +%H:%M:%S)"
    echo "=================================================================="
    start=$(date +%s)
    if python spike_gemma.py "${OUTLINES[@]}" --strategy "$strategy" "${COMMON_ARGS[@]}"; then
      status="finished"
    else
      status="FAILED (exit code $?), continuing with the next strategy"
    fi
    mins=$(( ($(date +%s) - start) / 60 ))
    echo "STRATEGY: $strategy $status in about $mins min"
  done

  echo
  echo "All done $(date)"
  echo "Scores per run are also in results/summary.csv"
} 2>&1 | tee "$LOG"

echo
echo "Log saved to: src/spikes/gemma4/$LOG"
