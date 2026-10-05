#!/bin/bash
# Sets up and starts the watermarks-remover service used by the remove-ai-marks skill.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

WR_REF="v0.7.0"
WR_DIR="$HOME/.cache/watermarks-remover"
SYNTHID_DIR="$HOME/.cache/reverse-SynthID"
C2PATOOL_VERSION="c2patool-v0.27.15"
C2PATOOL_SHA256="7a035b727a6cdda8ad08d98fe94b3c20febee4aea4e7c1de02571b295730faf0"
PORT=8765
LOG="$HOME/.cache/watermarks-service.log"

log() { echo "[watermarks] $*" >&2; }

# 1. Optional system tools: exiftool, qpdf, ghostscript.
if ! command -v exiftool >/dev/null || ! command -v qpdf >/dev/null || ! command -v gs >/dev/null; then
  log "installing exiftool, qpdf, ghostscript"
  apt-get update -qq >&2
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq libimage-exiftool-perl qpdf ghostscript >&2
fi

# 2. c2patool, pinned by release tag + sha256 (same as upstream Dockerfile).
if ! command -v c2patool >/dev/null; then
  log "installing $C2PATOOL_VERSION"
  tmp="$(mktemp -d)"
  curl -fsSL -o "$tmp/c2patool.tar.gz" \
    "https://github.com/contentauth/c2pa-rs/releases/download/${C2PATOOL_VERSION}/${C2PATOOL_VERSION}-x86_64-unknown-linux-gnu.tar.gz"
  echo "${C2PATOOL_SHA256}  $tmp/c2patool.tar.gz" | sha256sum -c - >&2
  tar -xzf "$tmp/c2patool.tar.gz" -C "$tmp"
  install -m 0755 "$tmp/c2patool/c2patool" /usr/local/bin/c2patool
  rm -rf "$tmp"
fi

# 3. Service checkout, pinned to a release tag.
mkdir -p "$HOME/.cache"
if [ "$(git -C "$WR_DIR" describe --tags --exact-match 2>/dev/null || true)" != "$WR_REF" ]; then
  log "fetching watermarks-remover $WR_REF"
  rm -rf "$WR_DIR"
  git -c advice.detachedHead=false clone -q --depth 1 --branch "$WR_REF" \
    https://github.com/guillaumemeyer/watermarks-remover.git "$WR_DIR" >&2
fi

# 4. reverse-SynthID image scorer (CPU-only; its pins need Python >= 3.12). Non-fatal.
if [ ! -x "$SYNTHID_DIR/.venv/bin/python" ]; then
  log "setting up reverse-SynthID scorer"
  py=python3.12
  command -v "$py" >/dev/null || py=python3
  bash "$WR_DIR/service/scripts/setup_synthid.sh" --dir "$SYNTHID_DIR" --python "$py" >&2 \
    || { log "SynthID scorer setup failed; continuing without it"; rm -rf "$SYNTHID_DIR/.venv"; }
fi

# 5. Start the service if it is not already answering.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo "export WATERMARKS_SERVICE_URL=\"http://127.0.0.1:$PORT\"" >> "$CLAUDE_ENV_FILE"
  echo "export WATERMARKS_REPO=\"$WR_DIR\"" >> "$CLAUDE_ENV_FILE"
fi

if ! curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
  log "starting service on 127.0.0.1:$PORT"
  if [ -x "$SYNTHID_DIR/.venv/bin/python" ]; then
    export REVERSE_SYNTHID_DIR="$SYNTHID_DIR"
  fi
  nohup setsid python3 "$WR_DIR/service/scripts/server.py" \
    --host 127.0.0.1 --port "$PORT" >"$LOG" 2>&1 </dev/null &
  for _ in $(seq 1 20); do
    curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && break
    sleep 0.5
  done
fi

if curl -sf "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
  log "service is up at http://127.0.0.1:$PORT"
else
  log "service failed to start; see $LOG"
fi
