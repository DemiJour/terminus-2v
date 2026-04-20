Task Name
fix-broken-git
Instructions
YOUR MAIN DELIVERABLE: Create /app/repair_report.txt documenting how you fixed the broken git submodules.

TASK:
1. Navigate to /app/broken-repo and fix the broken git submodules
2. The correct repository URLs are: file:///app/repos/lib-a.git, lib-b.git, lib-c.git
3. Fix bare repos: Ensure HEAD points to refs/heads/main or refs/heads/master
4. Synchronize git config with .gitmodules, deinitialize and reinitialize submodules
5. Fix detached HEAD: cd into each submodule (submodule-a, submodule-b, submodule-c) and checkout main or master branch
6. Verify with a fresh clone to /app/clone_test with --recurse-submodules
7. Commit your fixes with "submodule" in the message (working tree must be clean except .gitmodules.broken)

CREATE /app/repair_report.txt with EXACTLY these sections:

Step 1: Diagnosis - Document broken state (include: broken/before, and explanation words like why/because/cause/reason/affect/impact/problem)
Step 2: Valid URLs - How you found correct URLs (include: investigate/search/found/discover/look/check/inspect/examine or mention /app/repos)
Step 3: Fixing .gitmodules - Show BEFORE and AFTER (include: before/broken, after/fixed, file://)
Step 4: Configuration Sync - Show BEFORE and AFTER git config (include: before/config, after/sync, explanation with why/drift/inconsistent/mismatch/conflict/necessary/required/synchronize)
Step 5: Deinitialization - Document deinit process (section required)
Step 6: Reinitialization - Document reinit process (section required)
Step 7: Branch Verification - Verify submodules (submodule-a, submodule-b, submodule-c) are on branches, show symbolic-ref output with refs/heads/
Step 8: Fresh Clone Verification - Show clone to /app/clone_test succeeded
Step 9: Content Integrity Validation - MANDATORY section: Verify README.md in submodules (submodule-a, submodule-b, submodule-c) using checksums (MUST use md5sum or sha256sum commands, include: md5/sha256/hash/checksum, integrity/verify/ensure)

Summary - MANDATORY section with checkmarks (✓) for EACH step. Must include these keywords with checkmarks:
  ✓ Diagnosis (or Diagnosed)
  ✓ URL (or URLs)
  ✓ .gitmodules (or gitmodules)
  ✓ Config (or Configuration)
  ✓ Deinit (or Deinitialized)
  ✓ Reinit (or Reinitialized)
  ✓ Branch (or Branches)
  ✓ Clone (or Cloned)
  ✓ Integrity (or Validated)

End Summary with "Repair completed successfully"

Include in report: complex corruption terms (corrupt/deinit/modules/clean/repair) and Git plumbing commands (symbolic-ref/show-ref/rev-parse/fsck/cat-file/update-ref).

KEY REQUIREMENTS:
- Remove broken URLs from .gitmodules (github.com/nonexistent-org, git@broken-server.example.com, gitlab.com/removed)
- Backup .gitmodules to .gitmodules.broken before changes
- Fix bare repos: lib-a.git and lib-c.git need HEAD on refs/heads/main or master, lib-b.git needs main branch
- Submodule paths: submodule-a, submodule-b, submodule-c (each has README.md and index.js)
- Working tree must be clean after commit (only .gitmodules.broken allowed)

REMEMBER: The file /app/repair_report.txt is your MAIN OUTPUT and MUST be created!