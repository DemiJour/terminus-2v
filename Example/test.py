import subprocess
import os
from pathlib import Path


def test_repair_report_exists():
    """Report file exists and isn't empty."""
    report_path = Path("/app/repair_report.txt")
    assert report_path.exists()
    assert report_path.stat().st_size > 0

def test_repair_report_content():
    """Report has required sections and checkmarks."""
    report_content = Path("/app/repair_report.txt").read_text()

    required_sections = [
        "Step 1: Diagnosis",
        "Step 2: Valid URLs",
        "Step 3: Fixing .gitmodules",
        "Step 4: Configuration Sync",
        "Step 5: Deinitialization",
        "Step 6: Reinitialization",
        "Step 7: Branch Verification",
        "Step 8: Fresh Clone Verification",
        "Step 9: Content Integrity Validation",
        "Summary"
    ]

    for section in required_sections:
        assert section in report_content, f"Missing required section: {section}"

    # Check Step 1 has BEFORE state documentation
    step1_start = report_content.find("Step 1: Diagnosis")
    step2_start = report_content.find("Step 2: Valid URLs")
    step1_content = report_content[step1_start:step2_start]
    assert "broken" in step1_content.lower() or "before" in step1_content.lower(), "Step 1 missing BEFORE state"

    # Check Step 3 has BEFORE and AFTER .gitmodules content
    step3_start = report_content.find("Step 3: Fixing .gitmodules")
    step4_start = report_content.find("Step 4: Configuration Sync")
    step3_content = report_content[step3_start:step4_start]
    assert "before" in step3_content.lower() or "broken" in step3_content.lower(), "Step 3 missing BEFORE content"
    assert "after" in step3_content.lower() or "fixed" in step3_content.lower() or "file:///" in step3_content, "Step 3 missing AFTER content"

    # Check Step 4 has BEFORE and AFTER git config
    step5_start = report_content.find("Step 5: Deinitialization")
    step4_content = report_content[step4_start:step5_start]
    assert "before" in step4_content.lower() or "config" in step4_content.lower(), "Step 4 missing BEFORE config"
    assert "after" in step4_content.lower() or "sync" in step4_content.lower(), "Step 4 missing AFTER sync"

    # Check Step 7 contains symbolic-ref output for each submodule
    step7_start = report_content.find("Step 7: Branch Verification")
    step8_start = report_content.find("Step 8: Fresh Clone Verification")
    assert step7_start != -1 and step8_start != -1
    step7_content = report_content[step7_start:step8_start]

    for submodule in ["submodule-a", "submodule-b", "submodule-c"]:
        assert submodule in step7_content, f"Step 7 missing {submodule} verification"
        assert "refs/heads/" in step7_content, "Step 7 missing symbolic-ref output"

    # Check Step 9 has content integrity validation
    step9_start = report_content.find("Step 9: Content Integrity Validation")
    summary_start_for_step9 = report_content.find("Summary", step9_start)
    step9_content = report_content[step9_start:summary_start_for_step9]

    # Check for file listings and checksums
    for submodule in ["submodule-a", "submodule-b", "submodule-c"]:
        assert submodule in step9_content, f"Step 9 missing {submodule} validation"

    # Check for checksum keywords (md5sum, sha256sum, or actual hash values)
    checksum_found = any(keyword in step9_content.lower() for keyword in ["md5", "sha256", "checksum", "hash"])
    assert checksum_found, "Step 9 missing file checksums"

    # Check for README.md mentions
    assert "README.md" in step9_content or "readme" in step9_content.lower(), "Step 9 missing README.md verification"

    # Check Summary has checkmarks for each step
    summary_start = report_content.find("Summary")
    assert summary_start != -1
    summary_content = report_content[summary_start:]

    required_checkmarks = [
        "Diagnos",  # Diagnosis/Diagnosed
        "URL",
        ".gitmodules",
        "onfig",  # Configuration/Config
        "Deinit",
        "Reinit",
        "ranch",  # Branch
        "clone",  # Fresh clone
        "integrity"  # Content integrity
    ]

    for item in required_checkmarks:
        assert item.lower() in summary_content.lower(), f"Summary missing checkmark for: {item}"

    assert "✓" in summary_content, "Summary missing checkmarks"
    assert "Repair completed successfully" in report_content, "Report missing success phrase"


def test_gitmodules_fixed():
    """Check .gitmodules has correct file:// URLs."""
    gitmodules_path = Path("/app/broken-repo/.gitmodules")
    assert gitmodules_path.exists()

    content = gitmodules_path.read_text()

    assert "https://github.com/nonexistent-org/deleted-repo.git" not in content
    assert "git@broken-server.example.com:fake/repo.git" not in content
    assert "https://gitlab.com/removed/project.git" not in content

    assert "file:///app/repos/lib-a.git" in content
    assert "file:///app/repos/lib-b.git" in content
    assert "file:///app/repos/lib-c.git" in content

    assert 'path = submodule-a' in content
    assert 'path = submodule-b' in content
    assert 'path = submodule-c' in content

    assert 'wrong-path' not in content


def test_git_config_synchronized():
    """Git config URLs match .gitmodules."""
    os.chdir("/app/broken-repo")

    result = subprocess.run(
        ["git", "config", "--get-regexp", "submodule.*url"],
        capture_output=True,
        text=True
    )

    config_output = result.stdout

    assert "old-server.example.com" not in config_output
    assert "another-broken.com" not in config_output

    assert "file:///app/repos/lib-a.git" in config_output
    assert "file:///app/repos/lib-b.git" in config_output
    assert "file:///app/repos/lib-c.git" in config_output


def test_submodules_initialized():
    """All submodules initialized (no - prefix)."""
    os.chdir("/app/broken-repo")

    result = subprocess.run(
        ["git", "submodule", "status"],
        capture_output=True,
        text=True
    )

    status_output = result.stdout
    lines = status_output.strip().split('\n')
    for line in lines:
        if line.strip():
            assert not line.startswith('-')
            assert 'submodule-a' in status_output or 'submodule-b' in status_output or 'submodule-c' in status_output


def test_submodule_directories_exist():
    """Submodule dirs exist with README and index.js."""
    base_path = Path("/app/broken-repo")
    submodules = ["submodule-a", "submodule-b", "submodule-c"]

    for submodule in submodules:
        submodule_path = base_path / submodule
        assert submodule_path.exists()
        assert submodule_path.is_dir()

        readme_path = submodule_path / "README.md"
        assert readme_path.exists()

        index_path = submodule_path / "index.js"
        assert index_path.exists()

def test_fresh_clone_successful():
    """Fresh clone works with submodules initialized."""
    clone_path = Path("/app/clone_test")
    assert clone_path.exists()
    assert clone_path.is_dir()

    # Check submodules initialized in fresh clone
    os.chdir("/app/clone_test")
    result = subprocess.run(
        ["git", "submodule", "status"],
        capture_output=True,
        text=True
    )

    # No '-' prefix means initialized
    for line in result.stdout.strip().split('\n'):
        if line.strip():
            assert not line.startswith('-'), "Fresh clone has uninitialized submodules"

    for submodule in ["submodule-a", "submodule-b", "submodule-c"]:
        submodule_path = clone_path / submodule
        assert submodule_path.exists()

        readme_path = submodule_path / "README.md"
        assert readme_path.exists()

        index_path = submodule_path / "index.js"
        assert index_path.exists()


def test_clean_working_tree():
    """No uncommitted changes."""
    os.chdir("/app/broken-repo")

    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True
    )

    status_output = result.stdout.strip()
    lines = [line for line in status_output.split('\n') if line and '.gitmodules.broken' not in line]
    assert len(lines) == 0


def test_no_detached_heads():
    """Submodules on branches, not detached HEAD."""
    os.chdir("/app/broken-repo")

    for submodule in ["submodule-a", "submodule-b", "submodule-c"]:
        os.chdir(f"/app/broken-repo/{submodule}")

        result = subprocess.run(
            ["git", "symbolic-ref", "-q", "HEAD"],
            capture_output=True,
            text=True
        )

        assert result.returncode == 0, f"Submodule {submodule} is in detached HEAD state"


def test_submodule_commits_exist_in_remotes():
    """Submodule commits are valid."""
    os.chdir("/app/broken-repo")

    for submodule in ["submodule-a", "submodule-b", "submodule-c"]:
        os.chdir(f"/app/broken-repo/{submodule}")

        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True
        )
        commit_sha = result.stdout.strip()

        verify_result = subprocess.run(
            ["git", "cat-file", "-t", commit_sha],
            capture_output=True,
            text=True
        )

        assert verify_result.returncode == 0
        assert "commit" in verify_result.stdout


def test_no_synthetic_data():
    """Real git operations, not fake data."""
    backup_path = Path("/app/broken-repo/.gitmodules.broken")
    assert backup_path.exists()

    backup_content = backup_path.read_text()
    assert "nonexistent-org" in backup_content or "broken-server" in backup_content

    os.chdir("/app/broken-repo")
    result = subprocess.run(
        ["git", "log", "--oneline", "-n", "10"],
        capture_output=True,
        text=True
    )

    log_output = result.stdout
    assert "Fix broken submodules" in log_output or "submodule" in log_output.lower()


def test_forensics_discovery():
    """Report shows evidence of URL discovery."""
    report_content = Path("/app/repair_report.txt").read_text().lower()

    investigation_keywords = [
        "discover", "investigation", "found", "repos",
        "/app/repos", "bare repositor", "forensic"
    ]

    found_evidence = any(keyword in report_content for keyword in investigation_keywords)
    assert found_evidence, "Report lacks evidence of URL discovery through investigation"


def test_bare_repository_repair():
    """Bare repos have valid HEAD and branches."""
    # Check lib-a.git has valid HEAD
    result = subprocess.run(
        ["git", "-C", "/app/repos/lib-a.git", "symbolic-ref", "HEAD"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, "lib-a.git HEAD not properly restored"
    assert "refs/heads/main" in result.stdout or "refs/heads/master" in result.stdout

    # Check lib-b.git has main branch (should be recreated if deleted)
    result = subprocess.run(
        ["git", "-C", "/app/repos/lib-b.git", "show-ref", "--verify", "refs/heads/main"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, "lib-b.git main branch not restored"

    # Check lib-c.git has valid HEAD
    result = subprocess.run(
        ["git", "-C", "/app/repos/lib-c.git", "symbolic-ref", "HEAD"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, "lib-c.git HEAD not properly restored"
    assert "refs/heads/main" in result.stdout or "refs/heads/master" in result.stdout


def test_no_misleading_urls_in_config():
    """All broken URLs removed from config."""
    os.chdir("/app/broken-repo")

    result = subprocess.run(
        ["git", "config", "--get-regexp", "submodule"],
        capture_output=True,
        text=True
    )

    config_output = result.stdout.lower()

    # Ensure no broken URLs remain
    broken_patterns = [
        "wrong-path-b", "old-server", "another-broken",
        "fake-server", "legacy.example", "old-cdn"
    ]

    for pattern in broken_patterns:
        assert pattern not in config_output, f"Broken config pattern '{pattern}' still present"


def test_complex_corruption_handled():
    """Report mentions handling complex issues."""
    report_content = Path("/app/repair_report.txt").read_text().lower()

    # Check report mentions handling complex issues
    complex_fixes = [
        "corrupt", "deinit", "modules", "clean",
        "repair", "restor", "recreat"
    ]

    mentions = sum(1 for fix in complex_fixes if fix in report_content)
    assert mentions >= 3, "Report doesn't demonstrate handling of complex corruptions"


def test_git_internals_understanding():
    """Report demonstrates Git internals understanding."""
    report_content = Path("/app/repair_report.txt").read_text().lower()

    # Check for evidence of Git plumbing/forensic commands usage
    plumbing_commands = [
        "symbolic-ref", "show-ref", "rev-parse",
        "fsck", "update-ref", "cat-file"
    ]

    # Should mention at least 2 plumbing commands showing deeper investigation
    plumbing_found = sum(1 for cmd in plumbing_commands if cmd in report_content)
    assert plumbing_found >= 2, "Report lacks evidence of Git plumbing commands usage for forensics"


def test_explanation_depth_step1():
    """Step 1 contains explanations of WHY, not just WHAT."""
    report_content = Path("/app/repair_report.txt").read_text()

    step1_start = report_content.find("Step 1: Diagnosis")
    step2_start = report_content.find("Step 2: Valid URLs")
    step1_content = report_content[step1_start:step2_start].lower()

    # Check for explanation indicators
    explanation_keywords = ["why", "because", "cause", "reason", "affect", "impact", "problem"]
    explanations_found = sum(1 for keyword in explanation_keywords if keyword in step1_content)

    assert explanations_found >= 2, "Step 1 lacks explanation of WHY issues are problematic (just lists WHAT)"


def test_investigation_process_documented():
    """Step 2 documents investigation process, not just results."""
    report_content = Path("/app/repair_report.txt").read_text()

    step2_start = report_content.find("Step 2: Valid URLs")
    step3_start = report_content.find("Step 3: Fixing .gitmodules")
    step2_content = report_content[step2_start:step3_start].lower()

    # Check for investigation process keywords
    investigation_keywords = [
        "investigate", "search", "check", "found", "look",
        "command", "discover", "inspect", "examine"
    ]

    investigation_found = sum(1 for keyword in investigation_keywords if keyword in step2_content)
    assert investigation_found >= 2, "Step 2 doesn't document investigation process"


def test_step4_explains_synchronization():
    """Step 4 explains WHY synchronization was necessary."""
    report_content = Path("/app/repair_report.txt").read_text()

    step4_start = report_content.find("Step 4: Configuration Sync")
    step5_start = report_content.find("Step 5: Deinitialization")
    step4_content = report_content[step4_start:step5_start].lower()

    # Check for explanation of why sync is necessary
    sync_explanation_keywords = [
        "why", "drift", "inconsist", "mismatch", "conflict",
        "necessary", "required", "must", "synchroniz"
    ]

    explanations = sum(1 for keyword in sync_explanation_keywords if keyword in step4_content)
    assert explanations >= 2, "Step 4 doesn't explain WHY synchronization was necessary"


def test_step9_explains_git_integrity():
    """Step 9 mentions Git's object hash system for integrity."""
    report_content = Path("/app/repair_report.txt").read_text()

    step9_start = report_content.find("Step 9: Content Integrity Validation")
    summary_start = report_content.find("Summary", step9_start)
    step9_content = report_content[step9_start:summary_start].lower()

    # Check for Git integrity concepts
    integrity_keywords = [
        "hash", "sha", "object", "integrity", "checksum",
        "git", "verif", "ensur"
    ]

    integrity_mentions = sum(1 for keyword in integrity_keywords if keyword in step9_content)
    assert integrity_mentions >= 3, "Step 9 doesn't explain Git's integrity system sufficiently"