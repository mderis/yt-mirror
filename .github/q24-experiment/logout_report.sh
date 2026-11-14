#!/bin/sh
# Temporary, Q-24 point (d). Runs as a system service, outside the login session,
# so it survives a logout. It waits for the logout, then reports what the test
# app wrote to its log as a check run on the commit.
# usage: logout_report.sh <work folder> <owner/repo> <commit> <python>
WORK="$1"; REPO="$2"; SHA="$3"; PY="$4"
LOG="$WORK/data/app.log"
while [ ! -f "$WORK/logout-requested" ]; do sleep 0.5; done
# Report quickly: the job's token stops working a few seconds after the logout,
# when the runner itself is shut down with the session.
i=0
while [ $i -lt 100 ]; do
    grep -q "shutdown finished" "$LOG" 2>/dev/null && break
    i=$((i + 1)); sleep 0.2
done
sleep 0.7
{
    echo "macOS: $(sw_vers -productVersion) on $(uname -m)"
    echo "logout requested at: $(cat "$WORK/logout-requested")"
    echo "reported at:         $(date +%s)"
    echo "owner of the console now (root means nobody is logged in): $(stat -f %Su /dev/console)"
    echo "test app processes still running: $(pgrep -f q24-experiment/app.py | wc -l | tr -d ' ')"
    echo "write-ahead file of the database left behind: $(ls "$WORK/data" | grep -c 'work.db-wal')"
    echo "--- the test app's log (process id, time, message)"
    cat "$LOG"
} > "$WORK/evidence.txt" 2>&1
"$PY" -c '
import json, sys
text = open(sys.argv[1]).read()
print(json.dumps({
    "name": "Q-24 (d) real logout",
    "head_sha": sys.argv[2],
    "status": "completed",
    "conclusion": "neutral",
    "output": {"title": "What the test app did at a real logout", "summary": "```\n" + text + "\n```"},
}))' "$WORK/evidence.txt" "$SHA" > "$WORK/body.json"
curl -sS --max-time 15 -X POST -H "Authorization: Bearer $(cat /var/root/q24-token)" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/$REPO/check-runs" -d @"$WORK/body.json" > "$WORK/post.txt" 2>&1
rm -f /var/root/q24-token
