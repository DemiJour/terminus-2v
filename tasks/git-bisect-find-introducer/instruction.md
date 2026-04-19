Use `git bisect` under `/app/repo` to find when a very specific bug marker first showed up.

Somewhere in history, someone added a single line to the main source file under `src/` (in this environment that is `src/main.go`) that is **exactly** `BUG_INTRODUCED` (whole line, nothing else on that line). Use whichever of `src/main.go` or `src/main.py` exists in your checkout for bisecting and for `files_touched`.

Other commits mention the same characters inside longer lines (for example `// BUG_INTRODUCED`, `REF: BUG_INTRODUCED`, or `BUG_INTRODUCED` with trailing spaces). Those are noise; only the standalone full line counts as the bug you are hunting.

After you have the introducing commit, write `/app/answer.txt` with exactly three non-empty lines: (1) full 40-character commit hash in lowercase hex, (2) the one-line subject of that commit, (3) the author email. No extra blank lines.

Write `/app/report.json` with the same commit details plus metadata:

```json
{
  "hash": "<string, same as line 1 of /app/answer.txt>",
  "subject": "<string, same as line 2>",
  "author": "<string, same as line 3>",
  "files_touched": ["<path>", "..."],
  "bug_line_is_exact": <boolean>
}
```

Sort `files_touched`, list each path once. Set `bug_line_is_exact` to true only if the traced `src/main.go` or `src/main.py` file at that commit actually contains a line that is exactly `BUG_INTRODUCED`.

Inspect history only; do not rewrite it. Absolute paths above are required.
