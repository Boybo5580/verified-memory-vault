#!/usr/bin/env python3
"""Self-test for memory_check.py / memory_guard.py.

Run from anywhere:  python3 tests/self_test.py
(or: make it executable). Stdlib only, no pytest required. Builds tiny
synthetic vaults in a temporary directory and asserts the risk-classed exit
codes:

    0 = HEALTHY            no defects
    1 = DEGRADED           hygiene defects only
    2 = PROVENANCE BREACH  undated / duplicated / near-duplicated entries

Exit code of this script: 0 if every case passes, 1 otherwise.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / "tools"
CHECK = TOOLS / "memory_check.py"

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
