#!/usr/bin/env python3
"""memory_guard.py — git pre-commit guard for the Verified Memory Vault.

Protects the agent's own memory from accidental mass damage:

  1. Mass deletion: refuses a commit that deletes more than
     --max-deletions (default 3) memory files at once, or removes more
     than --max-deleted-lines (default 10) lines from memory files in
     one commit — the absolute cap catches small vaults where a
     proportionally "small" deletion is still fatal.
  2. History rewrite of MEMORY.md: the protocol is append-only. A commit
     that REMOVES lines from MEMORY.md (other than pure whitespace or
     entries moved to MEMORY-Archive.md in the same commit) is refused.

Usage:
  As a git hook:   ln -s ../../tools/memory_guard.py .git/hooks/pre-commit
  Manually:        python3 tools/memory_guard.py [--max-deletions N]

Exit code 0 = commit may proceed, 1 = refused (with reason).

Standard library only, Python 3.8+. No dependencies.
"""

import argparse
import subprocess
import sys
from pathlib import Path

PROTECTED_HINT = "MEMORY-Archive.md"


def run_git(args: list) -> str:
    res = subprocess.run(
        ["git"] + args, capture_output=True, text=True, check=False
    )
    if res.returncode != 0:
        print(f"memory_guard: git {args[0]} failed: {res.stderr.strip()}")
        sys.exit(1)
    return res.stdout


def staged_changes(numstat: str):
    """Yield (status, path, added, deleted) for staged files."""
    for line in numstat.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        adds, dels, path = parts
        adds = 0 if adds == "-" else int(adds)
        dels = 0 if dels == "-" else int(dels)
        status = (
            "add" if adds > 0 and dels == 0 and not Path(path).exists()
            else "edit"
        )
        yield path, adds, dels


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-deletions", type=int, default=3)
    ap.add_argument(
        "--max-deleted-lines", type=int, default=10,
        help="absolute cap on removed lines from memory files per commit",
    )
    args = ap.parse_args()

    # Not inside a git repo -> nothing to guard.
    top = run_git(["rev-parse", "--show-toplevel"])
    root = Path(top.strip())

    numstat = run_git(["diff", "--cached", "--numstat", "-M"])

    memory_files_deleted = []
    memory_lines_removed = 0
    memory_lines_removed_files = []
    archive_updated = any(
        PROTECTED_HINT.lower() in p.lower() for p, _, _ in staged_changes(numstat)
    )

    for path, adds, dels in staged_changes(numstat):
        name = Path(path).name
        is_memory = (
            name in ("MEMORY.md", PROTECTED_HINT)
            or "/01_Daily/" in f"/{path}"
            or path.startswith("01_Daily/")
        )
        # Whole-file deletions of memory files.
        if dels > 0 and adds == 0 and is_memory:
            memory_files_deleted.append(path)
        # Line removals inside memory files (absolute-cap accounting).
        if is_memory and dels > 0:
            memory_lines_removed += dels
            memory_lines_removed_files.append(path)

    problems = []

    if len(memory_files_deleted) > args.max_deletions:
        problems.append(
            f"{len(memory_files_deleted)} memory file(s) deleted in one commit "
            f"(limit {args.max_deletions}): {memory_files_deleted}. "
            "If this is intentional, commit with --no-verify after double-checking."
        )

    if memory_lines_removed > 0 and not archive_updated:
        problems.append(
            f"{memory_lines_removed} line(s) removed from MEMORY.md but "
            f"{PROTECTED_HINT} was not updated in the same commit. The protocol "
            "is append-only: move old entries to MEMORY-Archive.md, don't delete."
        )

    if memory_lines_removed > args.max_deleted_lines:
        problems.append(
            f"{memory_lines_removed} line(s) removed from memory files in one "
            f"commit (absolute limit {args.max_deleted_lines}): "
            f"{sorted(set(memory_lines_removed_files))}. If this is "
            "intentional, commit with --no-verify after double-checking."
        )

    if problems:
        rel_root = root.name
        print("memory_guard: COMMIT REFUSED — memory protection triggered:")
        for i, p in enumerate(problems, 1):
            print(f"  {i}. {p}")
        print(f"  (vault: {rel_root}; bypass with `git commit --no-verify`)")
        return 1

    print("memory_guard: ok — no memory damage detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
