#!/usr/bin/env bash
set -euo pipefail

cd /app/repo

# Bisect: first commit where src/main.py has exact whole line "BUG_INTRODUCED" (-Fx = fixed, whole line)
# Good = no such line (exit 0), Bad = line present (exit 1)
cat > /tmp/bisect-check.sh << 'CHECK'
#!/bin/bash
grep -Fxq 'BUG_INTRODUCED' src/main.py && exit 1 || exit 0
CHECK
chmod +x /tmp/bisect-check.sh

FIRST=$(git rev-list --max-parents=0 HEAD)
git bisect start
git bisect bad HEAD
git bisect good "$FIRST"
BISECT_OUT=$(git bisect run /tmp/bisect-check.sh 2>&1) || true
FIRST_BAD=$(echo "$BISECT_OUT" | grep "is the first bad commit" | grep -oE '[0-9a-f]{40}' | head -1)
if [ -z "$FIRST_BAD" ]; then
  FIRST_BAD=$(git rev-parse HEAD)
fi
git bisect reset 2>/dev/null || true

SUBJECT=$(git log -1 -s --format=%s "$FIRST_BAD")
AUTHOR_EMAIL=$(git log -1 -s --format=%ae "$FIRST_BAD")
printf "%s\n%s\n%s\n" "$FIRST_BAD" "$SUBJECT" "$AUTHOR_EMAIL" > /app/answer.txt

# Also produce structured report.json describing the commit.
export FIRST_BAD SUBJECT AUTHOR_EMAIL
python3 - << 'PY'
import json
import os
import subprocess
from pathlib import Path

commit = os.environ["FIRST_BAD"]
subject = os.environ["SUBJECT"]
author = os.environ["AUTHOR_EMAIL"]

files_raw = subprocess.check_output(
    ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit],
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
