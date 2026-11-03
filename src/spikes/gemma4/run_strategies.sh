#!/usr/bin/env bash
# Spike #38: run the linking, think and fewshot strategies on the two hard outlines
# and save everything printed to results/logs/strategies_<timestamp>.log
#
# Usage (Git Bash, from anywhere):
#   bash src/spikes/gemma4/run_strategies.sh
#
# Takes about 40 to 50 minutes on CPU. Ollama must be running.

cd "$(dirname "$0")" || exit 1

OUTLINES=(
  "outlines/Fall_2026/SFWRENG2OP3_AngelaZavaleta_Fall2026.pdf"
  "outlines/Fall_2026/SFWRENG2XC3_SamScott_Fall2026.pdf"
)
STRATEGIES=(linking think fewshot)
COMMON_ARGS=(--postprocess --num-ctx 16384 --key-dir keys)

mkdir -p results/logs
LOG="results/logs/strategies_$(date +%Y%m%d-%H%M%S).log"

# Stream Python output straight away (no buffering) and keep it UTF-8 for the log
export PYTHONUNBUFFERED=1
export PYTHONIOENCODING=utf-8

{
  echo "Spike #38 strategy runs, started $(date)"
  echo "Outlines: ${OUTLINES[*]}"
  echo "Strategies: ${STRATEGIES[*]}"
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

  # Check Ollama is up before spending 40 minutes
  if ! curl -s --max-time 5 http://localhost:11434/api/tags > /dev/null; then
    echo "ERROR: Ollama is not reachable at http://localhost:11434. Start Ollama and run this again."
    exit 1
  fi
  echo "Ollama is reachable."

  for strategy in "${STRATEGIES[@]}"; do
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
