"""Verify the agent wrote the correct bisect result and report."""
import json
import re
from pathlib import Path

# Full 40-char lowercase hex
HASH_PATTERN = re.compile(r"^[0-9a-f]{40}\s*$")


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


def test_answer_matches_expected_commit_subject_and_author() -> None:
    """Lines 1–3 must equal expected hash, subject, and author email."""
    answer_path = Path("/app/answer.txt")
    expected_hash_path = Path("/app/expected_commit.txt")
    expected_subject_path = Path("/app/expected_subject.txt")
    expected_author_path = Path("/app/expected_author.txt")
    assert expected_hash_path.exists(), "Expected commit file missing (task setup)"
    assert expected_subject_path.exists(), "Expected subject file missing (task setup)"
    assert expected_author_path.exists(), "Expected author file missing (task setup)"
    lines = answer_path.read_text().strip().splitlines()
    assert len(lines) >= 3, "Answer must have three lines"
    answer_hash = lines[0].strip()
    answer_subject = lines[1].strip()
    answer_author = lines[2].strip()
    expected_hash = expected_hash_path.read_text().strip()
    expected_subject = expected_subject_path.read_text().strip()
    expected_author = expected_author_path.read_text().strip()
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


def test_expected_commit_file_format() -> None:
    """Expected commit file must be a valid 40-char hex hash."""
    expected_path = Path("/app/expected_commit.txt")
    assert expected_path.exists(), "Expected commit file missing (task setup)"
    content = expected_path.read_text().strip()
    assert HASH_PATTERN.match(content), (
        f"expected_commit.txt must be 40-char hex, got: {content!r}"
    )


def test_report_json_exists_and_is_valid_json() -> None:
    """Valid JSON must exist at /app/report.json."""
    report_path = Path("/app/report.json")
    assert report_path.exists(), "report.json not found at /app/report.json"
    try:
        with report_path.open() as f:
            json.load(f)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"report.json is not valid JSON: {exc}") from exc


def test_report_json_schema_and_consistency() -> None:
    """report.json must follow the documented schema and match /app/answer.txt."""
    answer_lines = Path("/app/answer.txt").read_text().strip().splitlines()
    assert len(answer_lines) == 3, "answer.txt must have exactly three lines"
    answer_hash, answer_subject, answer_author = [ln.strip() for ln in answer_lines]

    report = json.loads(Path("/app/report.json").read_text())

    for key in ("hash", "subject", "author", "files_touched", "bug_line_is_exact"):
        assert key in report, f"report.json missing key: {key}"

    assert report["hash"] == answer_hash, "report.hash must equal answer.txt line 1"
    assert report["subject"] == answer_subject, "report.subject must equal answer.txt line 2"
    assert report["author"] == answer_author, "report.author must equal answer.txt line 3"

    files = report["files_touched"]
    assert isinstance(files, list), "files_touched must be a list"
    assert all(isinstance(f, str) for f in files), "files_touched must be list[str]"
    assert files == sorted(set(files)), "files_touched must be sorted and unique"
    assert "src/main.py" in files, "src/main.py must be listed in files_touched"

    assert report["bug_line_is_exact"] is True, "bug_line_is_exact must be true"
