#!/usr/bin/env bash
# Run the extraction model on a McMaster CAS GPU server instead of your laptop.
#
# What it does (asks for your MacID; ssh then asks for your password once):
#   1. Installs Ollama in your home folder on the server (no sudo, first run only).
#   2. Starts Ollama there on a private port, on the least busy GPU.
#   3. Pulls the model (gemma4:e2b by default, first run only).
#   4. Keeps an SSH tunnel open so http://localhost:11435 on your laptop reaches it.
# While the tunnel is open, run the extraction from src/backend in another terminal:
#   OLLAMA_URL=http://localhost:11435 .venv/Scripts/python -m app.extraction.cli path/to/outline.pdf
# Outline text only travels over SSH to the CAS server (never outside CAS).
#
# Usage (Git Bash on Windows, or a terminal on macOS/Linux; not PowerShell):
#   src/backend/scripts/gpu_ollama.sh          # set up, start, and open the tunnel
#   src/backend/scripts/gpu_ollama.sh status   # is the server-side Ollama running?
#   src/backend/scripts/gpu_ollama.sh stop     # stop Ollama on the server (be nice
#                                              # to other users when you are done)
# Settings you can override with environment variables:
#   GPU_HOST (grace.cas.mcmaster.ca)  LLM_MODEL (gemma4:e2b)  LOCAL_PORT (11435)
#   MACID (skip the prompt)
# LOCAL_PORT is not 11434 so it does not clash with an Ollama on your laptop.
#
# Why Ollama and not vLLM (the department guide uses vLLM): our LLM client
# (app/extraction/llm_client.py) talks to Ollama, so no code has to change.
#
# Why one SSH session does everything: the first version reused one connection
# for several ssh calls (ControlMaster), but Git Bash's ssh on Windows cannot
# do that ("mux_client_request_session ... Connection reset by peer"). Doing
# setup and tunnel in a single ssh call works everywhere with one password.

# Stop on the first error (-e), on unset variables (-u), and when any command
# in a pipe fails (-o pipefail), instead of carrying on in a broken state.
set -euo pipefail

# --- Settings (environment variable, else the default after ":-") ----------
GPU_HOST="${GPU_HOST:-grace.cas.mcmaster.ca}"
LLM_MODEL="${LLM_MODEL:-gemma4:e2b}"
LOCAL_PORT="${LOCAL_PORT:-11435}"
# First argument: start (default), status or stop.
ACTION="${1:-start}"

case "$ACTION" in
  start|status|stop) ;;
  *) echo "Usage: $0 [start|status|stop]" >&2; exit 1 ;;
esac

# Ask for the MacID unless it was given as an environment variable.
if [[ -z "${MACID:-}" ]]; then
  read -r -p "MacID: " MACID
fi
[[ -n "$MACID" ]] || { echo "A MacID is needed." >&2; exit 1; }
TARGET="$MACID@$GPU_HOST"

# The server port, worked out from the MacID so that:
#   - the laptop knows it before connecting (needed to set up the tunnel), and
#   - students on the same server almost never pick the same port.
# cksum turns the MacID into a number; the port lands in 20000-29999.
REMOTE_PORT=$((20000 + $(printf '%s' "$MACID" | cksum | cut -d' ' -f1) % 10000))

# --- The part that runs on the server ----------------------------------------
# Stored in a variable and sent over ssh, so there is nothing to copy to the
# server by hand. The quoted 'REMOTE' marker means nothing inside is expanded
# here on the laptop; the $variables are filled in on the server.
# ("|| true" because read -d '' always returns 1 at the end of the text.)
read -r -d '' REMOTE_SCRIPT <<'REMOTE' || true
set -euo pipefail
# Arguments sent from the laptop: action, model, server port, laptop port.
action="$1"; model="$2"; port="$3"; local_port="$4"
# Everything lives in ~/ollama: the program, the models and the log.
base="$HOME/ollama"
bin="$base/bin/ollama"
# 127.0.0.1 = only reachable from the server itself (and through our tunnel),
# not from the network. OLLAMA_MODELS keeps the downloaded models in ~/ollama.
export OLLAMA_HOST="127.0.0.1:$port" OLLAMA_MODELS="$base/models"

# Keep the model loaded for an hour after the last request (Ollama's default
# is 5 minutes). Loading from the home folder on grace took about 6.5 minutes,
# so unloading between runs would make every run pay that again. It uses about
# 3.6 GB of an 80 GB GPU; "gpu_ollama.sh stop" frees it straight away.
export OLLAMA_KEEP_ALIVE=1h

# True if our Ollama answers on its port.
running() { curl -s -m 3 "http://$OLLAMA_HOST/api/version" >/dev/null 2>&1; }

case "$action" in
  status)
    if running; then
      echo "Ollama is running on the server (port $port)."
      # Lists the models currently loaded on the GPU.
      "$bin" ps || true
    else
      echo "Ollama is not running on the server."
    fi
    ;;
  stop)
    # Only kills your own Ollama (-u your user id), never anyone else's.
    pkill -u "$(id -u)" -f "$bin serve" && echo "Stopped Ollama on the server." \
      || echo "Ollama was not running."
    ;;
  start)
    # 1. Install Ollama the first time (the official installer needs sudo, so
    #    we unpack the release archive into the home folder instead).
    if [[ ! -x "$bin" ]]; then
      echo "Installing Ollama into $base (first run only) ..."
      mkdir -p "$base"
      archive="$base/ollama.tar.zst"
      # Ollama ships Linux builds as .tar.zst (zstd-compressed tar).
      curl -fsSL https://ollama.com/download/ollama-linux-amd64.tar.zst -o "$archive"
      if command -v zstd >/dev/null; then
        zstd -dc "$archive" | tar -x -C "$base"
      else
        # No zstd on the server: unpack with Python's zstandard package instead,
        # installed into ~/ollama/.pydeps so it does not touch anything else.
        pydeps="$base/.pydeps"
        python3 -m pip install -q --target "$pydeps" zstandard
        PYTHONPATH="$pydeps" python3 -c \
          'import sys, zstandard; zstandard.ZstdDecompressor().copy_stream(sys.stdin.buffer, sys.stdout.buffer)' \
          <"$archive" | tar -x -C "$base"
      fi
      rm -f "$archive"
      [[ -x "$bin" ]] || { echo "Ollama install failed." >&2; exit 1; }
    fi
    # 2. Start the Ollama server if it is not already running.
    if ! running; then
      # Use the GPU with the most free memory, so we do not crowd other users.
      # nvidia-smi prints "index, free MiB" per GPU; sort by free memory, take the top.
      gpu=$(nvidia-smi --query-gpu=index,memory.free --format=csv,noheader,nounits \
            | sort -t, -k2 -nr | head -1 | cut -d, -f1)
      echo "Starting Ollama on GPU ${gpu:-?} (port $port) ..."
      # nohup + & keep it running after this ssh session ends; output goes to a log.
      CUDA_VISIBLE_DEVICES="${gpu:-0}" nohup "$bin" serve >"$base/serve.log" 2>&1 &
      # Wait up to 30 s for it to answer.
      for _ in $(seq 30); do running && break; sleep 1; done
      running || { echo "Ollama did not start; see $base/serve.log" >&2; exit 1; }
    fi
    # 3. Download the model if needed (does nothing if it is already there).
    echo "Making sure $model is available (the first download takes a few minutes) ..."
    "$bin" pull "$model" >/dev/null
    # 4. Ready. The tunnel was opened by the same ssh call that runs this
    #    script, so it is already working.
    cat <<EOF

Tunnel open: http://localhost:$local_port on your laptop -> Ollama ($model) on the GPU.
In another Git Bash terminal, from src/backend:
  OLLAMA_URL=http://localhost:$local_port .venv/Scripts/python -m app.extraction.cli path/to/outline.pdf
Press Ctrl+C here to close the tunnel. Ollama keeps running on the server;
stop it with: src/backend/scripts/gpu_ollama.sh stop
EOF
    # 5. Keep this ssh session (and so the tunnel) open until Ctrl+C.
    # $PPID is the server's sshd process for this session. When you press
    # Ctrl+C the session ends, sshd exits, and this loop stops too, so no
    # stray process is left behind on the server.
    while kill -0 "$PPID" 2>/dev/null; do sleep 30; done
    ;;
esac
REMOTE

# --- The part that runs on your laptop -----------------------------------------
# One ssh call. The script above is sent on stdin ("bash -s"); the values after
# "--" become its $1..$4.
#   StrictHostKeyChecking=accept-new  trust the server's key on the very first
#                                     connection, but refuse if it ever changes
SSH_OPTS=(-o StrictHostKeyChecking=accept-new)
if [[ "$ACTION" == start ]]; then
  echo "Connecting to $GPU_HOST as $MACID ..."
  # -L forwards localhost:LOCAL_PORT on the laptop to 127.0.0.1:REMOTE_PORT on
  # the server, for as long as this ssh session is open.
  # ExitOnForwardFailure: stop with an error if LOCAL_PORT is already in use,
  # instead of silently running without a tunnel.
  # ServerAliveInterval: send a keep-alive every 60 s so an idle tunnel is not
  # dropped while you are running extractions.
  SSH_OPTS+=(-L "$LOCAL_PORT:127.0.0.1:$REMOTE_PORT" -o ExitOnForwardFailure=yes
             -o ServerAliveInterval=60)
fi
ssh "${SSH_OPTS[@]}" "$TARGET" bash -s -- \
  "$ACTION" "$LLM_MODEL" "$REMOTE_PORT" "$LOCAL_PORT" <<<"$REMOTE_SCRIPT"
