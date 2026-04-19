"""Verify the Go ELF GOT patcher task (/app/got-patch) end-to-end."""

from __future__ import annotations

import os
import re
import stat
import subprocess
from pathlib import Path


def _run(cmd: list[str], *, cwd: str = "/app", timeout: int = 120) -> subprocess.CompletedProcess[str]:
    """Run a command with a bounded timeout and return the completed process."""
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _assert_setup_succeeded(proc: subprocess.CompletedProcess[str]) -> None:
    assert proc.returncode == 0, f"setup.sh failed:\n{proc.stdout}\n{proc.stderr}"


def _assert_go_build_succeeded(proc: subprocess.CompletedProcess[str]) -> None:
    assert proc.returncode == 0, f"go build failed:\n{proc.stderr}\n{proc.stdout}"


def _assert_mode_exactly_0755(path: str) -> None:
    got = stat.S_IMODE(os.stat(path).st_mode)
    assert got == 0o755, f"{path} must be exactly mode 0755 (rwxr-xr-x), got {oct(got)}"


_SINGLE_GO_IMPORT = re.compile(r'^\s*import\s+(?:[\w.]+\s+)?"([^"]+)"\s*$')
_MULTI_GO_IMPORT_START = re.compile(r'^\s*import\s*\(\s*$')
_MULTI_GO_IMPORT_LINE = re.compile(r'^\s*(?:[\w.]+\s+)?"([^"]+)"')
_MULTI_GO_IMPORT_END = re.compile(r'^\s*\)\s*$')


def _parse_go_import_paths(src: str) -> set[str]:
    """Return import paths from Go source (comments + strings may still confuse edge cases)."""
    paths: set[str] = set()
    src = re.sub(r"/\*[\s\S]*?\*/", "", src)
    lines = src.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _SINGLE_GO_IMPORT.match(line)
        if m:
            paths.add(m.group(1))
            i += 1
            continue
        if _MULTI_GO_IMPORT_START.match(line):
            i += 1
            while i < len(lines):
                if _MULTI_GO_IMPORT_END.match(lines[i]):
                    i += 1
                    break
                lm = _MULTI_GO_IMPORT_LINE.match(lines[i])
                if lm:
                    paths.add(lm.group(1))
                i += 1
            continue
        i += 1
    return paths


def test_setup_builds_harness_binaries():
    """Verify /app/setup.sh exists, is executable, and produces the harness ELF binaries."""
    setup = Path("/app/setup.sh")
    assert setup.is_file(), "/app/setup.sh must exist"
    assert os.access(setup, os.X_OK), "/app/setup.sh must be executable"
    proc = _run(["bash", str(setup)])
    assert proc.returncode == 0, f"setup.sh failed:\n{proc.stdout}\n{proc.stderr}"
    assert Path("/app/test_program_with_wrapper").is_file()
    assert Path("/app/libmallocwrapper.so").is_file()


def test_got_patch_binary_builds():
    """Verify the Go module builds a /app/got-patch CLI from ./cmd/got-patch."""
    proc = _run(["go", "build", "-o", "/app/got-patch", "./cmd/got-patch"])
    assert proc.returncode == 0, f"go build failed:\n{proc.stderr}\n{proc.stdout}"
    out = Path("/app/got-patch")
    assert out.is_file(), "/app/got-patch must exist after go build"
    assert os.access(out, os.X_OK), "/app/got-patch must be executable"


def test_source_elf_parsing_is_manual_no_disallowed_helpers():
    """Disallow debug/elf, other bundled ELF parsers, and third-party module imports per instruction."""
    forbidden_exact = frozenset({"debug/elf", "debug/macho", "debug/pe", "debug/plan9obj"})
    forbidden_prefixes = (
        "github.com/",
        "golang.org/x/",
        "google.golang.org/",
    )
    for path in sorted(Path("/app").rglob("*.go")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for imp in _parse_go_import_paths(text):
            assert imp not in forbidden_exact, f"{path}: must not import {imp!r}"
            for prefix in forbidden_prefixes:
                assert not imp.startswith(prefix), (
                    f"{path}: must not import non-stdlib module {imp!r}"
                )


def test_patcher_cli_requires_arguments():
    """With too few arguments the tool exits non-zero and prints usage."""
    _assert_setup_succeeded(_run(["bash", "/app/setup.sh"]))
    _assert_go_build_succeeded(_run(["go", "build", "-o", "/app/got-patch", "./cmd/got-patch"]))
    proc = _run(["/app/got-patch"])
    assert proc.returncode != 0
    combined = (proc.stdout + proc.stderr).lower()
    assert "usage" in combined


def test_unpatched_binary_has_no_interception_banner():
    """The linked harness must not print MALLOC INTERCEPTED before patching."""
    _assert_setup_succeeded(_run(["bash", "/app/setup.sh"]))
    proc = _run(["/app/test_program_with_wrapper"])
    assert proc.returncode == 0, proc.stderr
    assert "MALLOC INTERCEPTED" not in (proc.stdout + proc.stderr)


def test_patch_then_run_shows_many_intercepts():
    """After patching, the output must include many MALLOC INTERCEPTED lines (>=120)."""
    _assert_setup_succeeded(_run(["bash", "/app/setup.sh"]))
    _assert_go_build_succeeded(_run(["go", "build", "-o", "/app/got-patch", "./cmd/got-patch"]))
    patch = _run(
        ["/app/got-patch", "/app/test_program_with_wrapper", "/app/test_program_patched", "logged_malloc"]
    )
    assert patch.returncode == 0, f"patch failed:\n{patch.stdout}\n{patch.stderr}"
    combined_logs = patch.stdout + patch.stderr
    combined_lower = combined_logs.lower()
    assert "reloc" in combined_lower, "successful patch should mention relocations in output"
    mentions_symbols = (
        "symbol" in combined_lower
        or "dynsym" in combined_lower
        or "symtab" in combined_lower
        or re.search(r"\bsyms?\b", combined_lower) is not None
    )
    assert mentions_symbols, (
        "successful patch should name symbols or dynamic symbol tables (e.g. dynsym, symtab)"
    )
    assert re.search(r"type\s*=\s*\d+", combined_logs), (
        "successful patch output must include relocation type numbers (e.g. type=7)"
    )
    cl = combined_lower
    assert "wrote patched elf to" in cl, "stderr must log the output path with the required wrote-patched prefix"
    assert "/app/test_program_patched" in cl
    assert "r_x86_64_jump_slot" in cl and "r_x86_64_glob_dat" in cl, (
        "stderr must name R_X86_64_JUMP_SLOT and R_X86_64_GLOB_DAT (ABI relocation classes)"
    )
    assert "file mode" in cl and ("0755" in cl or "0o755" in cl), (
        "stderr must report file mode 0755 for the output ELF"
    )
    _assert_mode_exactly_0755("/app/test_program_patched")

    run = _run(["/app/test_program_patched"])
    assert run.returncode == 0, run.stderr
    out = run.stdout + run.stderr
    assert out.count("MALLOC INTERCEPTED") >= 120


def test_patched_binary_permissions_and_header_unchanged():
    """Output ELF must be executable; first 64 bytes of ELF header must match input."""
    _assert_setup_succeeded(_run(["bash", "/app/setup.sh"]))
    _assert_go_build_succeeded(_run(["go", "build", "-o", "/app/got-patch", "./cmd/got-patch"]))
    patch = _run(
        ["/app/got-patch", "/app/test_program_with_wrapper", "/app/test_program_patched", "logged_malloc"]
    )
    assert patch.returncode == 0, f"patch failed:\n{patch.stdout}\n{patch.stderr}"
    assert Path("/app/test_program_patched").is_file()
    assert os.access("/app/test_program_patched", os.X_OK)
    _assert_mode_exactly_0755("/app/test_program_patched")
    a = Path("/app/test_program_with_wrapper").read_bytes()[:64]
    b = Path("/app/test_program_patched").read_bytes()[:64]
    assert a == b, "ELF ehdr prefix (first 64 bytes) must be unchanged"


def test_patch_with_default_wrapper_symbol_succeeds():
    """Omitting wrapper_symbol must default to logged_malloc and still intercept malloc."""
    _assert_setup_succeeded(_run(["bash", "/app/setup.sh"]))
    _assert_go_build_succeeded(_run(["go", "build", "-o", "/app/got-patch", "./cmd/got-patch"]))
    out_elf = "/app/test_program_patched_default_wrapper"
    patch = _run(["/app/got-patch", "/app/test_program_with_wrapper", out_elf])
    assert patch.returncode == 0, f"patch failed:\n{patch.stdout}\n{patch.stderr}"
    combined = patch.stdout + patch.stderr
    assert re.search(r"type\s*=\s*\d+", combined), "patch output must include relocation type numbers"
    low = combined.lower()
    assert "wrote patched elf to" in low and out_elf in combined
    assert "r_x86_64_jump_slot" in low and "r_x86_64_glob_dat" in low
    _assert_mode_exactly_0755(out_elf)
    run = _run([out_elf])
    assert run.returncode == 0, run.stderr
    assert (run.stdout + run.stderr).count("MALLOC INTERCEPTED") >= 120


def test_missing_wrapper_reports_error():
    """Unknown wrapper symbol must yield a non-zero exit and an explanatory message."""
    _assert_setup_succeeded(_run(["bash", "/app/setup.sh"]))
    _assert_go_build_succeeded(_run(["go", "build", "-o", "/app/got-patch", "./cmd/got-patch"]))
    proc = _run(
        [
            "/app/got-patch",
            "/app/test_program_with_wrapper",
            "/app/out_bad",
            "definitely_missing_symbol_zzzzz",
        ]
    )
    assert proc.returncode != 0
    msg = (proc.stdout + proc.stderr).lower()
    assert "not found" in msg or "missing" in msg or "no relocations" in msg


def test_patch_rejects_non_elf_or_truncated_input():
    """Non-ELF or truncated input must exit non-zero with a clear error (no silent success)."""
    _assert_setup_succeeded(_run(["bash", "/app/setup.sh"]))
    _assert_go_build_succeeded(_run(["go", "build", "-o", "/app/got-patch", "./cmd/got-patch"]))
    bad_magic = Path("/app/case_bad_magic.bin")
    bad_magic.write_bytes(b"NOTELF" + b"\x00" * 58)
    proc = _run(
        ["/app/got-patch", str(bad_magic), "/app/out_bad_magic", "logged_malloc"]
    )
    assert proc.returncode != 0
    msg = (proc.stdout + proc.stderr).lower()
    assert "elf" in msg or "truncat" in msg, f"expected ELF parse error, got:\n{proc.stdout}\n{proc.stderr}"

    trunc = Path("/app/case_truncated_elf.bin")
    trunc.write_bytes(b"\x7fELF\x02\x01\x01" + b"\x00" * 20)
    proc2 = _run(
        ["/app/got-patch", str(trunc), "/app/out_trunc", "logged_malloc"]
    )
    assert proc2.returncode != 0
    msg2 = (proc2.stdout + proc2.stderr).lower()
    assert "elf" in msg2 or "truncat" in msg2, f"expected parse/size error, got:\n{proc2.stdout}\n{proc2.stderr}"
