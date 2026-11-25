#!/usr/bin/env bash
# Run a whole model-selection spike on the CAS GPU server (grace) with nobody watching,
# so the laptop can be closed. One password to start a job, one to fetch its results.
#
#   bash src/spikes/common/grace_unattended.sh start JOB   # send everything, start the runs
#   bash src/spikes/common/grace_unattended.sh fetch JOB   # copy the results back (any time)
#
# Jobs (each has its own folder on grace and its own Ollama, so two jobs can run at
# the same time without touching each other):
#   qwen3        qwen3:4b with --native-think off and on    ~/cas-spike         Ollama "ollama"
#   gemma-llama  gemma4:e2b and llama3.2:3b, asked exactly  ~/cas-spike-gemma-llama
#                as in #38 and #40 (no --native-think)      Ollama "ollama-b"
#
# For every model setting ("variant") of the job, pipeline.sh on grace runs:
#   Phase A (baseline and think, all five outlines) -> choose_strategy.py picks the
#   better strategy -> Phase C and Phase B with that strategy -> compare_inject.py ->
#   stops this job's own Ollama, so the GPU memory is freed for other users.
# It saves nvidia-smi every 15 minutes (gpu_load.log), because grace is shared.
#
# Safety: nothing here deletes anything on grace. A job refuses to start if its folder
# already exists. The only processes stopped are this job's own (matched by your user
# id and the job's own names). On the laptop, only the temporary packing folder is removed.
#
# Settings: MACID (default sagarh), GPU_HOST (grace.cas.mcmaster.ca).

set -euo pipefail

MACID="${MACID:-sagarh}"
GPU_HOST="${GPU_HOST:-grace.cas.mcmaster.ca}"
TARGET="$MACID@$GPU_HOST"
ACTION="${1:-}"
JOB="${2:-}"
HERE="$(cd "$(dirname "$0")" && pwd)"          # src/spikes/common
SPIKES="$(cd "$HERE/.." && pwd)"               # src/spikes
# Same port rule as gpu_ollama.sh (20000-29999 from the MacID); the second Ollama uses the next port
BASE_PORT=$((20000 + $(printf '%s' "$MACID" | cksum | cut -d' ' -f1) % 10000))

# --- The jobs ----------------------------------------------------------------------
# VARIANTS: "model think-setting" pairs; "-" = do not send --native-think (as #38/#40)
# DIGESTS:  model digests from the laptop runs; a different download is logged as a warning
case "$JOB" in
  qwen3)
    WORKDIR="cas-spike";             OLLAMA_NAME="ollama";   OLLAMA_PORT=$BASE_PORT
    VARIANTS="qwen3:4b=off qwen3:4b=on"
    DIGESTS="qwen3:4b=359d7dd4bcda" ;;
  gemma-llama)
    WORKDIR="cas-spike-gemma-llama"; OLLAMA_NAME="ollama-b"; OLLAMA_PORT=$((BASE_PORT + 1))
    VARIANTS="gemma4:e2b=- llama3.2:3b=-"
    DIGESTS="gemma4:e2b=b37049369adf llama3.2:3b=a80c4f17acd5" ;;

  # Rerun jobs: only the outline runs lost to Ollama "HTTP 500" errors on 2026-11-23
  # (Phase B of qwen3 and gemma, one Phase A outline of qwen3 reasoning-on). They run a
  # fixed list (QUEUE) instead of the phase pipeline. Note: --runs numbers runs from 1,
  # so the two 2OP3 reruns are saved as run 1 and run 2 (they are its runs 2 and 3).
  rerun-qwen-on)
    WORKDIR="cas-spike-rerun-qwen-on"; OLLAMA_NAME="ollama";   OLLAMA_PORT=$BASE_PORT
    VARIANTS="qwen3:4b=on"
    DIGESTS="qwen3:4b=359d7dd4bcda"
    QUEUE='--model qwen3:4b --native-think on --strategies baseline --outlines 2C03 --label phaseA-gpu-rerun
--model qwen3:4b --native-think on --strategies baseline --outlines 2OP3 --runs 2 --label phaseB-gpu-rerun
--model qwen3:4b --native-think on --strategies baseline --outlines "2XC3 2DA4 2DM3 2C03" --runs 3 --label phaseB-gpu-rerun' ;;
  rerun-rest)
    WORKDIR="cas-spike-rerun-rest";    OLLAMA_NAME="ollama-b"; OLLAMA_PORT=$((BASE_PORT + 1))
    VARIANTS="qwen3:4b=off gemma4:e2b=-"
    DIGESTS="qwen3:4b=359d7dd4bcda gemma4:e2b=b37049369adf"
    QUEUE='--model qwen3:4b --native-think off --strategies think --outlines "2XC3 2DA4 2DM3 2C03" --runs 3 --label phaseB-gpu-rerun
--model gemma4:e2b --strategies think --outlines 2DA4 --label phaseB-gpu-rerun
--model gemma4:e2b --strategies think --outlines "2DM3 2C03" --runs 3 --label phaseB-gpu-rerun' ;;
  *)
    echo "Usage: grace_unattended.sh start|fetch qwen3|gemma-llama|rerun-qwen-on|rerun-rest" >&2; exit 1 ;;
esac
# Phase jobs have no fixed list
QUEUE="${QUEUE:-}"

case "$ACTION" in

start)
  # ---- 1. Collect what grace needs into a temporary folder on the laptop -----------
  STAGE="$(mktemp -d)"
  mkdir -p "$STAGE/common/outlines/Fall_2026"
  # The harness without the laptop's venv, results, caches and .env
  ( cd "$HERE" && tar -c --exclude=.venv --exclude=results --exclude=__pycache__ --exclude=.env . ) \
    | tar -x -C "$STAGE/common"
  # The five test outlines, found under the laptop's outline folder (.env setting)
  OUTLINES_DIR="${SPIKE_OUTLINES_DIR:-$(grep -E '^SPIKE_OUTLINES_DIR=' "$HERE/.env" | cut -d= -f2-)}"
  for f in SFWRENG2OP3_AngelaZavaleta_Fall2026.pdf SFWRENG2XC3_SamScott_Fall2026.pdf \
           SFWRENG2DA4_RyanLeduc_Fall2026.pdf SFWRENG2DM3_RidhaKhedri_Fall2026.pdf \
           COMPSCI2C03-VincentMaccio_Fall2026.pdf; do
    found=$(find "$OUTLINES_DIR" -name "$f" -print -quit)
    [ -n "$found" ] || { echo "ERROR: $f not found under $OUTLINES_DIR"; exit 1; }
    cp "$found" "$STAGE/common/outlines/Fall_2026/"
  done
  # On grace the harness reads the outlines from common/outlines
  echo "SPIKE_OUTLINES_DIR=outlines" > "$STAGE/common/.env"
  # Pack it as text so it travels inside the script on ssh's input (no scp, no 2nd password)
  PAYLOAD=$(tar -cz -C "$STAGE" . | base64 -w 0)
  # Remove only the temporary folder made above, and only if it really is a temp folder
  case "$STAGE" in /tmp/*|"${TMPDIR:-/nonexistent}"/*) rm -r "$STAGE" ;; esac
  echo "Job $JOB: packed harness and outlines ($(( ${#PAYLOAD} / 1024 )) KB). Connecting to $GPU_HOST ..."

  # ---- 2. The script that runs on grace (sent on ssh's input) ----------------------
  # 'REMOTE' in quotes: nothing below is expanded on the laptop.
  read -r -d '' REMOTE_SCRIPT <<'REMOTE' || true
set -euo pipefail
workdir="$1"; ollama_name="$2"; port="$3"; variants="$4"; digests="$5"; payload="$6"
queue="${7:-}"   # rerun jobs: a fixed list of run_spike.sh option lines
work="$HOME/$workdir"
base="$HOME/ollama"
export OLLAMA_HOST="127.0.0.1:$port" OLLAMA_MODELS="$base/models" OLLAMA_KEEP_ALIVE=2h
running() { curl -s -m 5 "http://$OLLAMA_HOST/api/version" >/dev/null 2>&1; }

# Never overwrite or move an earlier job: stop if its folder is already there
if [ -e "$work" ]; then
  echo "ERROR: ~/$workdir already exists on grace. Fetch its results, then remove or rename it yourself." >&2
  exit 1
fi
[ -x "$base/bin/ollama" ] || { echo "ERROR: Ollama is not installed in ~/ollama (run gpu_ollama.sh once)." >&2; exit 1; }

# Show recent errors from earlier Ollama runs (why calls failed with HTTP 500 before)
echo "--- Recent errors in ~/ollama/serve*.log (for diagnosis) ---"
grep -ihE "error|out of memory|panic|fatal|failed" "$base"/serve*.log 2>/dev/null \
  | grep -v "level=INFO" | tail -n 12 || true
echo "---"

# This job's own Ollama. The second one runs under its own name (a link to the same
# program), so each job's cleanup can stop exactly its own Ollama and nothing else.
bin="$base/bin/$ollama_name"
[ -e "$bin" ] || ln -s ollama "$bin"
if ! running; then
  # GPUs our other Ollama already uses (read from our own processes only)
  ours=$(for p in $(pgrep -u "$(id -u)" -f "ollama/bin/ollama[-a-z]* serve" || true); do
           tr '\0' '\n' < "/proc/$p/environ" 2>/dev/null | sed -n 's/^CUDA_VISIBLE_DEVICES=//p'
         done)
  # Of the other GPUs, the one with the most free memory
  gpu=$(nvidia-smi --query-gpu=index,memory.free --format=csv,noheader,nounits \
        | grep -vE "^($(echo $ours | tr ' ' '|' | sed 's/^$/none/')),"  \
        | sort -t, -k2 -nr | head -1 | cut -d, -f1)
  echo "Starting Ollama '$ollama_name' on GPU ${gpu:-0} (port $port) ..."
  CUDA_VISIBLE_DEVICES="${gpu:-0}" nohup setsid "$bin" serve > "$base/serve-$ollama_name.log" 2>&1 < /dev/null &
  for _ in $(seq 30); do running && break; sleep 1; done
  running || { echo "ERROR: Ollama did not start; see ~/ollama/serve-$ollama_name.log" >&2; exit 1; }
fi

# Pull every model of the job and check it is the same download as the laptop runs
for v in $variants; do
  model="${v%%=*}"
  echo "Pulling $model ..."
  "$bin" pull "$model" > /dev/null
  digest=$(curl -s "http://$OLLAMA_HOST/api/tags" | tr '{' '\n' | grep "\"name\":\"$model\"" \
           | sed -n 's/.*"digest":"\([0-9a-f]\{12\}\).*/\1/p')
  expected=$(echo "$digests" | tr ' ' '\n' | sed -n "s/^$model=//p")
  if [ "$digest" = "$expected" ]; then echo "  $model digest $digest, same as the laptop runs."
  else echo "  WARNING: $model digest $digest, laptop runs used $expected (different download)."; fi
done

# Unpack the harness and outlines, and make the Python venv (same pymupdf as the laptop)
mkdir -p "$work"
echo "$payload" | base64 -d | tar -xz -C "$work"
python3 -m venv "$work/common/.venv"
"$work/common/.venv/bin/python" -m pip install -q --disable-pip-version-check pymupdf==1.27.2.2
echo "Python: $("$work/common/.venv/bin/python" --version), pymupdf installed."

# ---- The pipeline that keeps running after we log out ----
cat > "$work/pipeline.sh" <<'EOF'
#!/usr/bin/env bash
# Runs on grace: Phase A, the strategy choice, Phases C and B, injection verdicts, cleanup.
# Arguments: Ollama address, this job's Ollama name, the variants ("model=think" pairs).
work="$(cd "$(dirname "$0")" && pwd)"
cd "$work"
export OLLAMA_HOST="$1"; ollama_name="$2"; variants="$3"; queue="$4"
COMMON="$work/common"
PY="$COMMON/.venv/bin/python"
log() { echo "$(date '+%F %T') $*"; }

# run_spike.sh options for a variant, and its results folder (same naming as spike_llm.py)
variant_opts() {
  local model="${1%%=*}" think="${1##*=}"
  if [ "$think" = "-" ]; then echo "--model $model"; else echo "--model $model --native-think $think"; fi
}
variant_folder() {
  local model="${1%%=*}" think="${1##*=}"
  local slug; slug=$(echo "$model" | sed 's/[^A-Za-z0-9._-]/-/g')
  if [ "$think" = "-" ]; then echo "$slug"; else echo "${slug}_think-$think"; fi
}

# Record grace's GPU load every 15 minutes; stopped however the pipeline ends
( while true; do
    { echo "== $(date '+%F %T')"
      nvidia-smi --query-gpu=index,utilization.gpu,memory.used,memory.total,power.draw --format=csv,noheader
    } >> gpu_load.log
    sleep 900
  done ) &
LOAD_LOGGER=$!
trap 'kill "$LOAD_LOGGER" 2>/dev/null' EXIT

# Rerun jobs: just run the fixed list, then stop this job's Ollama
if [ -n "$queue" ]; then
  printf '%s\n' "$queue" > rerun.txt
  log "Rerun list (rerun.txt)"
  bash "$COMMON/run_queue.sh" rerun.txt
  pkill -u "$(id -u)" -f "ollama/bin/$ollama_name serve" && log "Stopped Ollama '$ollama_name'."
  log "PIPELINE DONE"
  exit 0
fi

# Phase A: both strategies, all five outlines, one run, for every variant
: > phaseA.txt
for v in $variants; do echo "$(variant_opts "$v") --label phaseA-gpu" >> phaseA.txt; done
log "Phase A: $variants"
bash "$COMMON/run_queue.sh" phaseA.txt

# For each variant, pick the better strategy and write the Phase C and B run lists
: > phaseBC.txt
for v in $variants; do
  summary="$COMMON/results/$(variant_folder "$v")/summary.csv"
  echo "== $v" >> choice.log
  best=$("$PY" "$COMMON/choose_strategy.py" "$summary" 2>> choice.log) || best=""
  if [ -z "$best" ]; then log "No Phase A results for $v; skipping its Phases C and B"; continue; fi
  echo "$v -> $best" >> choice.log
  log "$v: chose $best (totals in choice.log)"
  echo "$(variant_opts "$v") --strategies $best --outlines \"2OP3 2DA4\" --inject \"ignore alter disguised\" --label phaseC-gpu" >> phaseBC.txt
  echo "$(variant_opts "$v") --strategies $best --runs 3 --label phaseB-gpu" >> phaseBC.txt
done

log "Phases C and B"
bash "$COMMON/run_queue.sh" phaseBC.txt

# Injection verdicts, after Phase B so every normal run is there to compare against
for v in $variants; do
  best=$(grep "^$v -> " choice.log | tail -1 | awk '{print $3}')
  [ -n "$best" ] || continue
  folder=$(variant_folder "$v")
  "$PY" "$COMMON/compare_inject.py" "$COMMON/results/$folder" --strategy "$best" \
    > "compare_inject_$folder.txt" 2>&1
  log "Injection verdicts for $v saved to compare_inject_$folder.txt"
done

# Done: stop only this job's own Ollama, so the GPU memory is free for others
pkill -u "$(id -u)" -f "ollama/bin/$ollama_name serve" && log "Stopped Ollama '$ollama_name'."
log "PIPELINE DONE"
EOF

# nohup + setsid: keeps running after this ssh session ends
nohup setsid bash "$work/pipeline.sh" "$OLLAMA_HOST" "$ollama_name" "$variants" "$queue" \
  > "$work/pipeline.log" 2>&1 < /dev/null &
sleep 2
echo "Pipeline started on grace (log: ~/$workdir/pipeline.log). You can close the laptop."
REMOTE

  # One ssh call: the job settings, payload and rerun list become the script's $1..$7
  # (set -- line), because the payload is too big to pass on the ssh command line.
  { printf 'set -- %q %q %q %q %q %q %q\n' "$WORKDIR" "$OLLAMA_NAME" "$OLLAMA_PORT" "$VARIANTS" "$DIGESTS" "$PAYLOAD" "$QUEUE"
    echo "$REMOTE_SCRIPT"; } \
    | ssh -o StrictHostKeyChecking=accept-new "$TARGET" bash -s
  ;;

fetch)
  # Copy results and logs from grace into results/grace/<job>/ (never mixed with laptop runs)
  DEST="$HERE/results/grace/$JOB"
  mkdir -p "$DEST"
  # (qwen3/ holds the run lists of the Qwen job, which was started by an earlier version)
  ssh "$TARGET" "cd ~/$WORKDIR && tar -cz *.log *.txt qwen3 common/results 2>/dev/null; exit 0" \
    | tar -xz -C "$DEST"
  echo "Copied to $DEST:"
  tail -n 5 "$DEST/pipeline.log"
  ;;

*)
  echo "Usage: grace_unattended.sh start|fetch qwen3|gemma-llama" >&2
  exit 1
  ;;
esac
