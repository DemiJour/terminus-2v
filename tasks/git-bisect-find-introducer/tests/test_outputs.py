"""Verify the agent wrote the correct bisect result and report."""
import json
import re
import subprocess
from pathlib import Path

# Full 40-char lowercase hex
HASH_PATTERN = re.compile(r"^[0-9a-f]{40}\s*$")

REPO = Path("/app/repo")
SOURCE_CANDIDATES = ("src/main.cpp", "src/main.go", "src/main.py")


def _git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run git in /app/repo."""
    return subprocess.run(
        ["git", "-C", str(REPO), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def _file_at_commit(commit: str, rel: str) -> str | None:
    """Return file contents at commit, or None if path missing at that commit."""
    p = _git("show", f"{commit}:{rel}", check=False)
    if p.returncode != 0:
        return None
    return p.stdout


def _first_commit_with_exact_bug_line() -> tuple[str, str, str]:
    """Oldest-first scan: first commit where main source has a whole line exactly BUG_INTRODUCED."""
    rev = _git("rev-list", "--reverse", "HEAD")
    commits = [c for c in rev.stdout.strip().splitlines() if c]
    assert commits, "Repository has no commits (broken task image)"
    for commit in commits:
        for rel in SOURCE_CANDIDATES:
            body = _file_at_commit(commit, rel)
            if body is None:
                continue
            if any(line == "BUG_INTRODUCED" for line in body.splitlines()):
                h = _git("log", "-1", "--format=%H", commit).stdout.strip().lower()
                subj = _git("log", "-1", "--format=%s", commit).stdout.strip()
                auth = _git("log", "-1", "--format=%ae", commit).stdout.strip()
                assert HASH_PATTERN.match(h), f"Computed hash invalid: {h!r}"
                return h, subj, auth
    raise AssertionError(
        "No commit introduces exact line BUG_INTRODUCED (broken task image)"
    )


def _expected_report_from_answer() -> dict[str, object]:
    """Canonical report dict for the commit named in /app/answer.txt (matches oracle semantics)."""
    lines = Path("/app/answer.txt").read_text().strip().splitlines()
    assert len(lines) >= 3, "answer.txt must have three lines"
    h = lines[0].strip().lower()
    subj = lines[1].strip()
    auth = lines[2].strip()
    files_raw = _git("diff-tree", "--no-commit-id", "--name-only", "-r", h).stdout.splitlines()
    files = sorted({f for f in files_raw if f})
    return {
        "hash": h,
        "subject": subj,
        "author": auth,
        "files_touched": files,
        "bug_line_is_exact": True,
    }


def test_answer_file_exists() -> None:
    """Answer must be written to /app/answer.txt."""
    answer_path = Path("/app/answer.txt")
    assert answer_path.exists(), "/app/answer.txt does not exist"
    assert answer_path.is_file(), "/app/answer.txt is not a file"


def test_answer_has_exactly_three_lines() -> None:
    """Answer file must contain exactly three lines (hash, subject, author email). No blank lines."""
    content = Path("/app/answer.txt").read_text()
    lines = content.strip().splitlines()
    assert len(lines) == 3, (
        f"Expected exactly three lines (no blank lines), got {len(lines)}"
    )
    for i, ln in enumerate(lines):
        assert ln.strip() == ln, f"Line {i+1} has leading/trailing whitespace or is blank"


def test_answer_line1_is_valid_commit_hash() -> None:
    """First line must be a 40-character lowercase hex commit hash."""
    lines = Path("/app/answer.txt").read_text().strip().splitlines()
    assert len(lines) >= 1, "Answer must have at least one line"
    line1 = lines[0].strip()
    assert HASH_PATTERN.match(line1), (
        f"Line 1 must be 40-char lowercase hex hash, got: {line1!r}"
    )


def test_answer_line1_has_exactly_40_characters() -> None:
    """First line must be exactly 40 characters (full SHA-1)."""
    lines = Path("/app/answer.txt").read_text().strip().splitlines()
    assert len(lines) >= 1, "Answer must have at least one line"
    line1 = lines[0].strip()
    assert len(line1) == 40, f"Hash must be 40 characters, got {len(line1)}"


def test_answer_line1_contains_only_lowercase_hex() -> None:
    """First line must contain only lowercase hex digits (0-9, a-f)."""
    lines = Path("/app/answer.txt").read_text().strip().splitlines()
    assert len(lines) >= 1, "Answer must have at least one line"
    line1 = lines[0].strip()
    assert line1.islower(), "Hash must be lowercase"
    valid_chars = set("0123456789abcdef")
    invalid = [c for c in line1 if c not in valid_chars]
    assert not invalid, f"Hash must be hex only, found: {invalid}"


def test_answer_line2_and_line3_non_empty() -> None:
    """Second and third lines must be non-empty (subject and author email)."""
    lines = Path("/app/answer.txt").read_text().strip().splitlines()
    assert len(lines) >= 3, "Answer must have three lines"
    assert lines[1].strip(), "Line 2 (subject) must be non-empty"
    assert lines[2].strip(), "Line 3 (author email) must be non-empty"


def test_answer_matches_golden_commit_subject_and_author() -> None:
    """Lines 1–3 must match the first commit that introduced a standalone BUG_INTRODUCED line (from git)."""
    expected_hash, expected_subject, expected_author = _first_commit_with_exact_bug_line()
    lines = Path("/app/answer.txt").read_text().strip().splitlines()
    assert len(lines) >= 3, "Answer must have three lines"
    answer_hash = lines[0].strip().lower()
    answer_subject = lines[1].strip()
    answer_author = lines[2].strip()
    assert answer_hash == expected_hash, (
        f"Commit hash mismatch: got {answer_hash}, expected {expected_hash}"
    )
    assert answer_subject == expected_subject, (
        f"Commit subject mismatch: got {answer_subject!r}, expected {expected_subject!r}"
    )
    assert answer_author == expected_author, (
        f"Author email mismatch: got {answer_author!r}, expected {expected_author!r}"
    )


def test_answer_file_has_no_extra_trailing_newlines() -> None:
    """File must end with a single newline after the third line (no extra blank lines)."""
    raw = Path("/app/answer.txt").read_bytes()
    assert raw.endswith(b"\n"), "File must end with a single newline"
    if len(raw) > 1:
        assert not raw.endswith(b"\n\n"), "File must not end with blank lines"


def test_report_json_exists_and_is_valid_json() -> None:
    """Valid JSON must exist at /app/report.json and parse as an object."""
    report_path = Path("/app/report.json")
    assert report_path.exists(), "report.json not found at /app/report.json"
    try:
        data = json.loads(report_path.read_text())
    except json.JSONDecodeError as exc:
        raise AssertionError(f"report.json is not valid JSON: {exc}") from exc
    assert isinstance(data, dict), "report.json root must be a JSON object"


def test_report_json_schema_and_consistency() -> None:
    """report.json must follow the documented schema and match git metadata for /app/answer.txt line 1."""
    expected = _expected_report_from_answer()
    report = json.loads(Path("/app/report.json").read_text())

    for key in ("hash", "subject", "author", "files_touched", "bug_line_is_exact"):
        assert key in report, f"report.json missing key: {key}"

    assert str(report["hash"]).lower() == expected["hash"], (
        "report.hash must equal answer.txt line 1 (case-insensitive)"
    )
    assert report["subject"] == expected["subject"], (
        "report.subject must equal answer.txt line 2"
    )
    assert report["author"] == expected["author"], (
        "report.author must equal answer.txt line 3"
    )

    files = report["files_touched"]
    assert isinstance(files, list), "files_touched must be a list"
    assert all(isinstance(f, str) for f in files), "files_touched must be list[str]"
    assert files == sorted(set(files)), "files_touched must be sorted and unique"
    assert files == expected["files_touched"], (
        "report.files_touched must match git diff-tree for the answer commit"
    )
    assert (
        ("src/main.cpp" in files)
        or ("src/main.go" in files)
        or ("src/main.py" in files)
    ), (
        "files_touched must list the traced source file (src/main.cpp or legacy src/main.go / src/main.py)"
    )

    assert report["bug_line_is_exact"] is True, "bug_line_is_exact must be true"
