#!/bin/sh
# What does the merged M0 app do when it is asked to quit? usage: m0_check.sh <repo> <python> <site-packages> <work dir>
R="$1"; PY="$2"; SITE="$3"; W="$4"; HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$W"
set -- "quit event (what Cmd+Q, the Quit item and the Dock's Quit send)" "Ctrl+C (SIGINT)" "termination signal (SIGTERM)" "window closed"
[ -n "${Q24_REAL_KEYS:-}" ] && set -- "$@" "real Cmd+Q key press"
for way in "$@"; do
    D="$W/data-$(echo "$way" | tr -c 'a-zA-Z' '_' | cut -c1-12)"; rm -rf "$D"
    if [ "$way" = "window closed" ]; then
        YTM_HOME="$R" YTM_DATA_DIR="$D" "$PY" -c "
import threading, time, sys
import webview
from ytmirror.app.main import main
def close_soon():
    while not webview.windows or not webview.windows[0].events.shown.is_set(): time.sleep(0.2)
    time.sleep(2); webview.windows[0].destroy()
threading.Thread(target=close_soon, daemon=True).start()
sys.exit(main([]))" >"$W/out.txt" 2>&1 &
    else
        YTM_HOME="$R" YTM_DATA_DIR="$D" "$PY" -m ytmirror.app.main >"$W/out.txt" 2>&1 &
    fi
    PID=$!
    i=0; until grep -q '"app.started"' "$D"/logs/*.jsonl 2>/dev/null; do i=$((i+1)); [ $i -gt 450 ] && break; sleep 0.2; done
    sleep 5
    case "$way" in
        quit*) "$PY" "$HERE/dock_quit.py" "$PID" "$SITE" >/dev/null ;;
        real*)
            osascript -e "tell application \"System Events\" to set frontmost of (first process whose unix id is $PID) to true" >/dev/null 2>&1
            sleep 1
            osascript -e 'tell application "System Events" to keystroke "q" using command down' ;;
        Ctrl*) kill -INT "$PID" ;;
        termination*) kill -TERM "$PID" ;;
    esac
    i=0; while kill -0 "$PID" 2>/dev/null && [ $i -lt 100 ]; do i=$((i+1)); sleep 0.2; done
    ended="ended by itself"
    if kill -0 "$PID" 2>/dev/null; then ended="DID NOT END, was killed"; kill -9 "$PID"; fi
    wait "$PID" 2>/dev/null; code=$?
    events=$(grep -o '"event": *"[a-z._]*"' "$D"/logs/*.jsonl | sed 's/.*: *"//; s/"//' | tr '\n' ' ')
    if grep -q '"app.stopping"' "$D"/logs/*.jsonl; then verdict="shutdown code RAN"; else verdict="shutdown code SKIPPED"; fi
    echo "M0, $way: $verdict ($ended, exit code $code; log events: $events)"
    tail -3 "$W/out.txt" | cut -c1-200
done
