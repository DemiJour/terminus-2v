"""Tests for the Go module and workspace repair task."""
import re
import subprocess
from pathlib import Path

ROOT = Path("/app")
BINARY = ROOT / "bin" / "ledger"


def _read_unix_text(path: Path) -> str:
    """Read text with CRLF normalized so checks are stable across newline styles."""
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _normalize_go_work_use_entry(entry: str) -> str:
    """Map equivalent root paths to '.' for workspace use entries."""
    e = entry.strip().rstrip(",")
    if e in (".", "./", "./."):
        return "."
    return e


def _run_go(args: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    """Run a go subcommand from the module root and return the completed process."""
    return subprocess.run(
        ["go", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


def test_go_mod_declares_required_module_path() -> None:
    """go.mod must declare module ledger.local/harbor as required by the task instructions."""
    text = _read_unix_text(ROOT / "go.mod")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    assert any(ln == "module ledger.local/harbor" for ln in lines), (
        "go.mod must contain a module line: module ledger.local/harbor"
    )


def test_go_mod_pins_toolchain_major_to_122() -> None:
    """go.mod must keep the go 1.22 toolchain directive required by the instructions."""
    text = _read_unix_text(ROOT / "go.mod")
    assert re.search(r"^\s*go\s+1\.22\s*$", text, flags=re.MULTILINE)


def test_go_work_exists_lists_only_root_and_drops_deprecated_pack() -> None:
    """go.work must exist, must not reference ./deprecated-pack, and use block must list only '.'."""
    path = ROOT / "go.work"
    assert path.is_file(), "/app/go.work must exist"
    work = _read_unix_text(path)
    assert "./deprecated-pack" not in work
    assert "deprecated-pack" not in work
    m = re.search(r"use\s*\((.*?)\)", work, flags=re.DOTALL | re.IGNORECASE)
    assert m, "go.work must contain a use (...) block"
    inner = m.group(1)
    paths = [
        _normalize_go_work_use_entry(ln)
        for ln in inner.splitlines()
        if ln.strip()
    ]
    assert paths == ["."], "go.work must list only the root module '.'"


def test_go_test_all_packages_passes() -> None:
    """go test ./... from /app must succeed after the module/workspace repair."""
    proc = _run_go(["test", "./..."])
    assert proc.returncode == 0, proc.stderr + proc.stdout


def test_go_build_and_ledger_cli_output() -> None:
    """go build -o /app/bin/ledger ./cmd/ledger must succeed; running the binary prints ledger: ready (42)."""
    BINARY.parent.mkdir(parents=True, exist_ok=True)
    if BINARY.exists():
        BINARY.unlink()
    proc = _run_go(["build", "-o", str(BINARY), "./cmd/ledger"])
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert BINARY.is_file()
    run = subprocess.run(
        [str(BINARY)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert run.returncode == 0, run.stderr
    assert run.stdout == "ledger: ready (42)\n"
    assert run.stderr == ""
