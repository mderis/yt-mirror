#!/bin/sh
# Smoke test of a clone: starts yt-mirror with the real launcher, without a
# window, and checks that it serves the interface and guards its API.
# Then runs the environment report, which must find no problem.
#
# This is the acceptance check of milestone M0 that can run unattended:
# "a fresh clone on a Mac runs with ./start" (R-IN-02). CI runs it on every
# supported macOS runner. It uses its own data folder and removes it again.
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

say "Starting yt-mirror without a window on port $PORT ..."
YTM_NO_WINDOW=1 YTM_PORT=$PORT YTM_SESSION_TOKEN=$TOKEN YTM_DATA_DIR="$DATA_DIR/data" \
    "$ROOT/start" >"$LOG" 2>&1 &
APP_PID=$!

# The first start downloads uv, Python and packages and builds the interface.
tries=0
until [ "$(status_of "$URL/")" = "200" ]; do
    kill -0 "$APP_PID" 2>/dev/null || fail "./start ended before the app was reachable"
    tries=$((tries + 1))
    [ "$tries" -lt 600 ] || fail "the app was not reachable after 10 minutes"
    sleep 1
done
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

kill "$APP_PID"
wait "$APP_PID" 2>/dev/null || true
APP_PID=""
grep -q '"event":"app.stopping"' "$DATA_DIR"/data/logs/*.jsonl || fail "the app did not log app.stopping"
say "ok: the app stopped cleanly and logged it"

say ""
YTM_DATA_DIR="$DATA_DIR/data" "$ROOT/start" --doctor || fail "the environment report found a problem"
say ""
say "Smoke test passed."
