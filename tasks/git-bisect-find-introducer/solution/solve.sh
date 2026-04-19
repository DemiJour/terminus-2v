#!/usr/bin/env bash
set -euo pipefail

cd /app/repo

# Track the real source path (src/main.go in current tasks; older cached images may still use src/main.py).
MAIN=src/main.go
if [ ! -f "$MAIN" ]; then
  MAIN=src/main.py
fi

# Bisect: first commit where MAIN has exact whole line "BUG_INTRODUCED" (-Fx = fixed, whole line).
# Good = no such line (exit 0), Bad = line present (exit 1).
cat > /tmp/bisect-check.sh <<CHECK
#!/usr/bin/env bash
grep -Fxq 'BUG_INTRODUCED' ${MAIN} && exit 1 || exit 0
CHECK
chmod +x /tmp/bisect-check.sh

FIRST=$(git rev-list --max-parents=0 HEAD)
git bisect start
git bisect bad HEAD
git bisect good "$FIRST"
BISECT_OUT=$(git bisect run /tmp/bisect-check.sh 2>&1) || true
if git rev-parse --verify refs/bisect/bad >/dev/null 2>&1; then
  FIRST_BAD=$(git rev-parse refs/bisect/bad)
else
  FIRST_BAD=$(echo "$BISECT_OUT" | awk '/^[0-9a-f]{40} is the first bad commit$/ { print $1; exit }')
  if [ -z "$FIRST_BAD" ]; then
    FIRST_BAD=$(git rev-parse HEAD)
  fi
fi
git bisect reset 2>/dev/null || true

SUBJECT=$(git log -1 -s --format=%s "$FIRST_BAD")
AUTHOR_EMAIL=$(git log -1 -s --format=%ae "$FIRST_BAD")
printf "%s\n%s\n%s\n" "$FIRST_BAD" "$SUBJECT" "$AUTHOR_EMAIL" > /app/answer.txt

export FIRST_BAD SUBJECT AUTHOR_EMAIL
python3 << 'PY'
import json
import os
import subprocess
from pathlib import Path

commit = os.environ["FIRST_BAD"]
subject = os.environ["SUBJECT"]
author = os.environ["AUTHOR_EMAIL"]

files_raw = subprocess.check_output(
    ["git", "-C", "/app/repo", "diff-tree", "--no-commit-id", "--name-only", "-r", commit],
    text=True,
).splitlines()
files = sorted({f for f in files_raw if f})

report = {
    "hash": commit,
    "subject": subject,
    "author": author,
    "files_touched": files,
    "bug_line_is_exact": True,
}

Path("/app/report.json").write_text(json.dumps(report, indent=2))
PY
