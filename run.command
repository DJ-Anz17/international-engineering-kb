#!/bin/zsh
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
mkdir -p "$SCRIPT_DIR/.logs"

if ! curl -fsS "http://127.0.0.1:8765/api/status" >/dev/null 2>&1; then
  launchctl kickstart -k "gui/$(id -u)/com.international-engineering-kb" >/dev/null 2>&1 || \
    nohup "$SCRIPT_DIR/start-kb.command" </dev/null >>"$SCRIPT_DIR/.logs/kb.log" 2>>"$SCRIPT_DIR/.logs/kb-error.log" &
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    curl -fsS "http://127.0.0.1:8765/api/status" >/dev/null 2>&1 && break
    sleep 1
  done
fi

open "http://127.0.0.1:8765"
