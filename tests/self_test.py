#!/usr/bin/env python3
"""Self-test for memory_check.py / memory_guard.py.

Run from anywhere:  python3 tests/self_test.py
(or: make it executable). Stdlib only, no pytest required. Builds tiny
synthetic vaults (and, for the guard cases, real temporary git repos) and
asserts both contracts:

memory_check.py risk-classed exit codes:
    0 = HEALTHY            no defects
    1 = DEGRADED           hygiene defects only
    2 = PROVENANCE BREACH  undated / duplicated / near-duplicated entries

memory_guard.py pre-commit refusals:
    mass deletion, MEMORY.md history rewrite without archiving,
    absolute removed-lines cap — and the legitimate paths
    (plain append, archive-and-trim) stay allowed.

Exit code of this script: 0 if every case passes, 1 otherwise.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / "tools"
CHECK = TOOLS / "memory_check.py"
GUARD = TOOLS / "memory_guard.py"

MINIMAL_VAULT = {
    "MEMORY.md": "# Memory\n\n- 2026-08-25: User prefers plain-text notes.\n",
    "00_Inbox/_README.md": "inbox\n",
    "01_Daily/2026-08-25.md": "Daily note.\n",
}

CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


def build_vault(overrides=None, extra=None):
    root = Path(tempfile.mkdtemp(prefix="vmv-selftest-"))
    for rel, content in MINIMAL_VAULT.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    for rel, content in (overrides or {}).items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    for rel in (extra or []):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("", encoding="utf-8")
    return root


def run_check(root):
    r = subprocess.run(
        [sys.executable, str(CHECK)],
        cwd=str(TOOLS),  # irrelevant; script locates its own parent vault? no:
        capture_output=True, text=True,
    )
    return r.returncode, r.stdout + r.stderr


def run_check_on(vault_root):
    """Copy tools/ next to the synthetic vault so find_vault_root() resolves."""
    import shutil
    shutil.copytree(TOOLS, vault_root / "tools", dirs_exist_ok=True)
    r = subprocess.run(
        [sys.executable, str(vault_root / "tools" / "memory_check.py")],
        capture_output=True, text=True,
    )
    return r.returncode, r.stdout + r.stderr


@case("healthy baseline -> exit 0")
def _t_healthy():
    return run_check_on(build_vault())


@case("dead wikilink -> exit 1 (hygiene)")
def _t_deadlink():
    v = dict(MINIMAL_VAULT)
    v["01_Daily/2026-08-25.md"] = "See [[Missing Note]].\n"
    code, out = run_check_on(build_vault(overrides=v))
    assert code == 1, (code, out)
    assert "PROBLEM" in out


@case("undated entry -> exit 2 (provenance)")
def _t_undated():
    v = dict(MINIMAL_VAULT)
    v["MEMORY.md"] = "# Memory\n\n- User likes dark mode.\n"
    code, out = run_check_on(build_vault(overrides=v))
    assert code == 2, (code, out)
    assert "PROVENANCE BREACH" in out


@case("byte-duplicate entry with different date -> exit 2")
def _t_dup():
    v = dict(MINIMAL_VAULT)
    v["MEMORY.md"] = ("# Memory\n\n"
                      "- 2026-08-24: Deploy happens on Fridays.\n"
                      "- 2026-08-25: Deploy happens on Fridays.\n")
    code, out = run_check_on(build_vault(overrides=v))
    assert code == 2, (code, out)


@case("near-duplicate (same fact, extended wording) -> exit 2")
def _t_near_dup():
    v = dict(MINIMAL_VAULT)
    v["MEMORY.md"] = ("# Memory\n\n"
                      "- 2026-08-24: API gateway runs on port 8443.\n"
                      "- 2026-08-25: The API gateway service runs on port 8443 internally.\n")
    code, out = run_check_on(build_vault(overrides=v))
    assert code == 2, (code, out)
    assert "near-duplicate" in out


@case("distinct facts stay distinct -> exit 0")
def _t_distinct():
    v = dict(MINIMAL_VAULT)
    v["MEMORY.md"] = ("# Memory\n\n"
                      "- 2026-08-24: CI pipeline uses pytest with xdist.\n"
                      "- 2026-08-25: Release notes are written on Sundays.\n")
    code, out = run_check_on(build_vault(overrides=v))
    assert code == 0, (code, out)


# --- memory_guard.py: pre-commit refusals on a real temporary git repo ----

GUARD_BASE_MEMORY = ("# Memory\n\n"
                     + "".join(
                         f"- 2026-08-{d:02d}: Fact number {d} is durable.\n"
                         for d in range(1, 16)))


def build_git_vault(memory=GUARD_BASE_MEMORY, daily_files=3):
    """A real git repo with an initialized vault and one baseline commit."""
    root = Path(tempfile.mkdtemp(prefix="vmv-guardtest-"))
    (root / "00_Inbox").mkdir()
    (root / "01_Daily").mkdir()
    (root / "MEMORY.md").write_text(memory, encoding="utf-8")
    for d in range(1, daily_files + 1):
        (root / f"01_Daily/2026-{'08'}-{d:02d}.md").write_text(
            "\n".join(f"Session note line {i}." for i in range(1, 6)) + "\n",
            encoding="utf-8")
    git(root, "init", "-q", "-b", "main")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Self Test")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "baseline vault")
    return root


def git(root, *args):
    r = subprocess.run(["git"] + list(args), cwd=str(root),
                       capture_output=True, text=True)
    assert r.returncode == 0, (args, r.stderr)
    return r.stdout


def stage_and_guard(root, extra_args=()):
    """Stage everything, then run memory_guard.py against the index."""
    git(root, "add", "-A")
    r = subprocess.run([sys.executable, str(GUARD), *extra_args],
                       cwd=str(root), capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


@case("guard: plain append is allowed -> exit 0")
def _g_append_ok():
    root = build_git_vault()
    try:
        with open(root / "MEMORY.md", "a", encoding="utf-8") as f:
            f.write("- 2026-08-25: New fact appended by session.\n")
        code, out = stage_and_guard(root)
        assert code == 0, (code, out)
        assert "ok" in out
    finally:
        shutil.rmtree(root, ignore_errors=True)


@case("guard: mass file deletion refused -> exit 1")
def _g_mass_delete():
    root = build_git_vault(daily_files=5)
    try:
        for d in range(1, 6):
            os.remove(root / f"01_Daily/2026-08-{d:02d}.md")
        code, out = stage_and_guard(root)
        assert code == 1, (code, out)
        assert "REFUSED" in out
    finally:
        shutil.rmtree(root, ignore_errors=True)


@case("guard: MEMORY.md rewrite without archive refused -> exit 1")
def _g_history_rewrite():
    root = build_git_vault()
    try:
        lines = GUARD_BASE_MEMORY.splitlines(keepends=True)
        trimmed = "".join(lines[:10])  # silently drop the older half
        (root / "MEMORY.md").write_text(trimmed, encoding="utf-8")
        code, out = stage_and_guard(root)
        assert code == 1, (code, out)
        assert "append-only" in out or "MEMORY-Archive" in out
    finally:
        shutil.rmtree(root, ignore_errors=True)


@case("guard: absolute removed-lines cap refused even with archive touched")
def _g_absolute_cap():
    root = build_git_vault(daily_files=4)
    try:
        # Archive exists in the same commit, but far too many daily-note
        # lines are deleted at once -> absolute cap must still fire.
        arch = root / "MEMORY-Archive.md"
        arch.write_text("# Archive\n\nmoved entries.\n", encoding="utf-8")
        for d in range(1, 5):
            (root / f"01_Daily/2026-08-{d:02d}.md").write_text(
                "\n".join(f"line {i}" for i in range(1, 6)) + "\n",
                encoding="utf-8")
        code, out = stage_and_guard(root, ("--max-deletions", "10"))
        assert code == 1, (code, out)
        assert "absolute limit" in out
    finally:
        shutil.rmtree(root, ignore_errors=True)


@case("guard: legitimate archive-and-trim commit allowed -> exit 0")
def _g_archive_path_ok():
    root = build_git_vault()
    try:
        lines = GUARD_BASE_MEMORY.splitlines(keepends=True)
        kept = "".join(lines[:7])
        moved = [ln for ln in lines[7:] if ln.startswith("- ")]
        (root / "MEMORY.md").write_text(kept, encoding="utf-8")
        with open(root / "MEMORY-Archive.md", "w", encoding="utf-8") as f:
            f.write("# Memory Archive\n\n" + "".join(moved))
        code, out = stage_and_guard(root)
        assert code == 0, (code, out)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main():
    failures = 0
    for name, fn in CASES:
        try:
            fn()
            print(f"  PASS  {name}")
        except AssertionError as e:
            failures += 1
            print(f"  FAIL  {name}: {e}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"  ERROR {name}: {type(e).__name__}: {e}")
    total = len(CASES)
    print(f"{total - failures}/{total} cases passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
