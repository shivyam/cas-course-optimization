#!/usr/bin/env bash
# Run a list of spike runs one after another, e.g. against the CAS GPU server.
#
# Each non-blank, non-# line of QUEUE_FILE is a set of run_spike.sh options. Every run
# still writes its own log in results/<model>/logs/; this script only prints one
# START / ok / FAILED line per run, so progress is easy to follow.
#
# Usage (Git Bash):
#   OLLAMA_HOST=localhost:11435 bash src/spikes/common/run_queue.sh src/spikes/qwen3/grace_phases.txt
# OLLAMA_HOST=localhost:11435 is the tunnel opened by src/backend/scripts/gpu_ollama.sh
# (branch feat/llm_processing): Ollama runs on grace's GPU, this laptop only sends text.

QUEUE_FILE="${1:?Usage: run_queue.sh QUEUE_FILE}"
RUNNER="$(dirname "$0")/run_spike.sh"

while IFS= read -r line; do
  # Skip blank lines and comments
  case "$line" in ''|\#*) continue ;; esac

  echo "$(date '+%F %T') START  $line"
  # eval so quoted values in the line (like --outlines "2OP3 2DA4") stay one argument.
  # < /dev/null stops the run from reading the rest of the queue file as its input.
  # run_spike.sh always exits 0 (its output goes through tee), so look for its
  # ERROR / FAILED lines instead of the exit code.
  output=$(eval "bash \"$RUNNER\" $line" 2>&1 < /dev/null)
  if echo "$output" | grep -qE "^ERROR|FAILED \(exit code"; then
    echo "$(date '+%F %T') FAILED $line"
    echo "$output" | grep -E "^ERROR|FAILED \(exit code|Log saved" | sed 's/^/    /'
  elif echo "$output" | grep -qE "SKIPPED:|RETRY"; then
    # Finished, but some calls needed retries or some outline runs were skipped
    # after repeated Ollama server errors (see ollama_client.py)
    echo "$(date '+%F %T') ok*   $line"
    echo "$output" | grep -E "SKIPPED:|RETRY|server error" | sed 's/^/    /'
  else
    echo "$(date '+%F %T') ok     $line"
  fi
done < "$QUEUE_FILE"

echo "$(date '+%F %T') QUEUE DONE"
