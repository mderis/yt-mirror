#!/bin/sh
# Smoke test of a clone: starts yt-mirror with the real launcher, without a
# window, and checks that it serves the interface and guards its API.
# Then runs the environment report, which must find no problem.
#
# This is the acceptance check that can run unattended: "a fresh clone on a
# Mac runs with ./start" (R-IN-02). CI runs it on every supported macOS
# runner. It uses its own data folder and removes it again.
#
# From milestone M1 it also starts the app once with its window, through the
# app bundle, and checks the name macOS knows it by (R-NA-01) and that a
# second start starts no second app (R-NA-08). A window appears for a moment.
#
# Two parts are slow and only run when asked for, as CI does:
#   YTM_SMOKE_TOOLS=1  Download the real ffmpeg and Deno and let the app check
#                      them, ffmpeg from each of its two sources (R-IN-03,
#                      docs/DECISIONS.md D-053). About 170 MB.
#   YTM_SMOKE_MOVE=1   Copy the whole folder to another place and start the
#                      copy (R-IN-05).
#
# Run from anywhere: scripts/smoke_test.sh

set -eu

ROOT=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd -P)
PORT=47802
TOKEN="smoke-test-token-not-a-secret"
URL="http://127.0.0.1:$PORT"
DATA_DIR=$(mktemp -d "${TMPDIR:-/tmp}/ytm-smoke.XXXXXX")
LOG="$DATA_DIR/start.log"
APP_PID=""

say() {
    printf '%s\n' "$*"
}

cleanup() {
    if [ -n "$APP_PID" ]; then
        kill "$APP_PID" 2>/dev/null || true
        wait "$APP_PID" 2>/dev/null || true
    fi
    rm -rf "$DATA_DIR"
}
trap cleanup EXIT

fail() {
    say "SMOKE TEST FAILED: $*"
    say "--- output of ./start ---"
    cat "$LOG" 2>/dev/null || true
    exit 1
}

status_of() {
    curl -s -o /dev/null -w '%{http_code}' "$@"
}

api() {
    curl -fsS -H "Authorization: Bearer $TOKEN" "$@"
}

# Prints one field of one tool from the answer of /api/tools.
tool_field() {
    api "$URL/api/tools" | "$ROOT/tools/venv/bin/python" -c '
import json, sys
tool = next(t for t in json.load(sys.stdin)["tools"] if t["name"] == sys.argv[1])
print(tool[sys.argv[2]])' "$1" "$2"
}

# Asks the running app to install a tool and waits until the app has checked it.
install_tool() {
    api -X POST -o /dev/null "$URL/api/tools/$1/install" || fail "the app refused to install $1"
    tries=0
    until [ "$(tool_field "$1" status)" = "ok" ]; do
        [ "$(tool_field "$1" status)" != "failed" ] || fail "$1 could not be installed: $(tool_field "$1" error_code)"
        tries=$((tries + 1))
        [ "$tries" -lt 1800 ] || fail "$1 was not installed after 30 minutes"
        sleep 1
    done
    say "ok: $1 $(tool_field "$1" version) from $(tool_field "$1" source) is installed and runs"
}

start_without_window() {
    YTM_NO_WINDOW=1 YTM_PORT=$PORT YTM_SESSION_TOKEN=$TOKEN YTM_DATA_DIR="$DATA_DIR/data" \
        "$@" >>"$LOG" 2>&1 &
    APP_PID=$!
    tries=0
    until [ "$(status_of "$URL/")" = "200" ]; do
        kill -0 "$APP_PID" 2>/dev/null || fail "./start ended before the app was reachable"
        tries=$((tries + 1))
        [ "$tries" -lt 600 ] || fail "the app was not reachable after 10 minutes"
        sleep 1
    done
}

stop_app() {
    kill "$APP_PID"
    wait "$APP_PID" 2>/dev/null || true
    APP_PID=""
}

say "Starting yt-mirror without a window on port $PORT ..."
# The first start downloads uv, Python and packages and builds the interface.
start_without_window "$ROOT/start"
say "ok: the interface is served"

[ "$(status_of "$URL/api/health")" = "401" ] || fail "the API answered without a session token"
say "ok: the API refuses a request without the session token"

[ "$(status_of -H "Authorization: Bearer $TOKEN" -H "Origin: https://evil.example" "$URL/api/health")" = "403" ] ||
    fail "the API accepted a request from another origin"
say "ok: the API refuses another origin"

health=$(curl -fsS -H "Authorization: Bearer $TOKEN" "$URL/api/health") || fail "the health request failed"
case "$health" in
    *'"status":"ok"'*) say "ok: health is $health" ;;
    *) fail "unexpected health answer: $health" ;;
esac

if [ -n "${YTM_SMOKE_TOOLS:-}" ]; then
    say ""
    say "Downloading the real tools from their first sources ..."
    install_tool ffmpeg
    install_tool deno
fi

stop_app
grep -q '"event":"app.stopping"' "$DATA_DIR"/data/logs/*.jsonl || fail "the app did not log app.stopping"
say "ok: the app stopped cleanly and logged it"

if [ -n "${YTM_SMOKE_TOOLS:-}" ]; then
    say ""
    say "Downloading ffmpeg from its second source, into a folder of its own ..."
    # Exported and taken back by hand: in sh, a variable set in front of a call of a
    # shell function would stay set for the rest of this script.
    export YTM_TOOL_SOURCE=jellyfin-ffmpeg YTM_TOOL_DIR="$DATA_DIR/second-source-tools"
    start_without_window "$ROOT/start"
    install_tool ffmpeg
    [ "$(tool_field ffmpeg source)" = "jellyfin-ffmpeg" ] || fail "ffmpeg did not come from the second source"
    stop_app
    unset YTM_TOOL_SOURCE YTM_TOOL_DIR
fi

say ""
say "Starting yt-mirror with its window, through the app bundle ..."
REPORT="$DATA_DIR/window.json"
YTM_SESSION_TOKEN=$TOKEN YTM_DATA_DIR="$DATA_DIR/data" YTM_WINDOW_REPORT="$REPORT" \
    "$ROOT/start" >>"$LOG" 2>&1 &
APP_PID=$!
tries=0
until [ -s "$REPORT" ]; do
    kill -0 "$APP_PID" 2>/dev/null || fail "./start ended before the window was up"
    tries=$((tries + 1))
    [ "$tries" -lt 120 ] || fail "the window was not up after two minutes"
    sleep 1
done
sleep 1
grep -q '"name": "yt-mirror (dev)"' "$REPORT" || fail "macOS does not know the app as yt-mirror (dev): $(cat "$REPORT")"
[ "$(ps -c -o comm= -p "$APP_PID")" = "yt-mirror (dev)" ] || fail "the process is called $(ps -c -o comm= -p "$APP_PID")"
say "ok: macOS knows the running app as yt-mirror (dev), not as Python"

second=$(YTM_DATA_DIR="$DATA_DIR/data" "$ROOT/start" 2>&1) || fail "a second start failed: $second"
case "$second" in
    *"already running"*) say "ok: a second start starts no second app" ;;
    *) fail "a second start did not say that yt-mirror is running: $second" ;;
esac
kill -0 "$APP_PID" 2>/dev/null || fail "the first app ended when the second one was started"

stop_app
[ "$(grep -c '"event":"app.stopping"' "$DATA_DIR"/data/logs/*.jsonl)" -ge 2 ] ||
    fail "the app with the window did not log app.stopping"
say "ok: the app with the window stopped cleanly on a termination signal"

say ""
if [ -n "${YTM_SMOKE_TOOLS:-}" ]; then
    YTM_DATA_DIR="$DATA_DIR/data" "$ROOT/start" --doctor || fail "the environment report found a problem"
else
    # Without the tool downloads the report may miss ffmpeg and Deno. It must still print.
    YTM_DATA_DIR="$DATA_DIR/data" "$ROOT/start" --doctor || say "(the report found a problem, see above)"
fi

if [ -n "${YTM_SMOKE_MOVE:-}" ]; then
    say ""
    say "Copying the whole folder to another place and starting the copy ..."
    COPY="$DATA_DIR/moved to here/yt-mirror"
    mkdir -p "$(dirname "$COPY")"
    cp -R "$ROOT" "$COPY"
    rm -rf "$COPY/data"
    ROOT_BEFORE="$ROOT"
    ROOT="$COPY"
    PORT=$((PORT + 1))
    URL="http://127.0.0.1:$PORT"
    DATA_BEFORE="$DATA_DIR"
    start_without_window "$COPY/start"
    grep -q "This folder was moved or copied" "$LOG" || fail "the copy did not rebuild its Python environment"
    case "$(sed -n 's/^home = //p' "$COPY/tools/venv/pyvenv.cfg")" in
        "$(cd "$COPY" && pwd -P)"/*) say "ok: the Python environment of the copy belongs to the copy" ;;
        *) fail "the Python environment of the copy still points to the old place" ;;
    esac
    health=$(api "$URL/api/health") || fail "the copy does not answer"
    say "ok: the copy runs: $health"
    stop_app
    if [ -n "${YTM_SMOKE_TOOLS:-}" ]; then
        YTM_DATA_DIR="$DATA_BEFORE/data" "$COPY/start" --doctor || fail "the tools of the copy do not work"
        say "ok: the tools that were copied along still work"
    fi
    ROOT="$ROOT_BEFORE"
fi

say ""
say "Smoke test passed."
