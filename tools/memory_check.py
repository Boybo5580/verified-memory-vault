#!/usr/bin/env python3
"""memory_check.py — health check for the Verified Memory Vault.

Scans the vault (default: the directory this script's parent is in) and
prints a health report. Exit code 0 = healthy, 1 = problems found.

Checks:
  1. MEMORY.md exists and follows the protocol (dated entries, one line,
     under the ~100-line budget, no duplicate entries).
  2. Daily notes exist in 01_Daily/ with valid YYYY-MM-DD names.
  3. Wikilinks resolve (Obsidian basename rule, [[Target|Alias]] and
     [[Target#Anchor]] handled).
  4. No empty notes; all files UTF-8 readable.
  5. Inbox size warning (capture without sorting).

Standard library only. Python 3.8+.
"""

import re
import sys
from datetime import datetime
from pathlib import Path

MEMORY_BUDGET_LINES = 100
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ENTRY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}:\s+\S")
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")


def find_vault_root() -> Path:
    """Vault root = parent of tools/ (this script lives in <vault>/tools/)."""
    return Path(__file__).resolve().parent.parent


def read_text(path: Path):
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def _is_entry_line(line: str) -> bool:
    """True for list-item lines (the only place entries live).

    Placeholder hints in parentheses — e.g. '- (how the user likes to
    work)' — are template scaffolding, not entries.
    """
    s = line.lstrip()
    if not (s.startswith("- ") or s.startswith("* ")):
        return False
    return not _entry_text(s).startswith("(")


def _entry_text(line: str) -> str:
    """List item content without the bullet."""
    return line.lstrip().lstrip("-*").strip()


def check_memory_md(root: Path, problems, warnings):
    mem = root / "MEMORY.md"
    if not mem.exists():
        problems.append("MEMORY.md missing (the durable memory file)")
        return
    text = read_text(mem)
    if text is None:
        problems.append("MEMORY.md is not valid UTF-8")
        return
    lines = [ln for ln in text.splitlines() if ln.strip()]
    body = [ln for ln in lines if not ln.strip().startswith("#")]
    if len(body) > MEMORY_BUDGET_LINES:
        warnings.append(
            f"MEMORY.md has {len(body)} content lines (budget {MEMORY_BUDGET_LINES})"
            " — move oldest entries to MEMORY-Archive.md"
        )
    bad = [ln for ln in body if _is_entry_line(ln) and not ENTRY_RE.match(_entry_text(ln))]
    if bad:
        problems.append(
            f"{len(bad)} MEMORY.md entry line(s) without a date "
            f"(format 'YYYY-MM-DD: fact'), e.g. {bad[0]!r}"
        )
    seen, dups = set(), []
    for ln in body:
        if not _is_entry_line(ln):
            continue
        key = _entry_text(ln)
        key = re.sub(r"^\d{4}-\d{2}-\d{2}:\s*", "", key).strip().lower()
        if key and key in seen:
            dups.append(ln[:60])
        elif key:
            seen.add(key)
    if dups:
        problems.append(f"{len(dups)} duplicate MEMORY.md entr(ies), e.g. {dups[0]!r}")


def check_daily_notes(root: Path, problems):
    daily = root / "01_Daily"
    if not daily.is_dir():
        problems.append("01_Daily/ folder missing")
        return
    for f in daily.iterdir():
        if f.is_file() and not DATE_RE.match(f.stem) and f.name != "_README.md":
            problems.append(
                f"01_Daily/{f.name}: note name must be YYYY-MM-DD.md"
            )


def collect_vault_notes(root: Path):
    skip_dirs = {".obsidian", ".git", "tools"}
    notes = {}
    for p in root.rglob("*.md"):
        rel = p.relative_to(root)
        if any(part in skip_dirs for part in rel.parts):
            continue
        notes[p.stem] = p
    return notes


def check_wikilinks(root: Path, notes: dict, problems, warnings):
    for stem, path in sorted(notes.items()):
        text = read_text(path)
        if text is None:
            problems.append(f"{path.name} is not valid UTF-8")
            continue
        if not text.strip():
            warnings.append(f"{path.relative_to(root)} is empty")
            continue
        for target in WIKILINK_RE.findall(text):
            t = target.strip()
            if t not in notes:
                problems.append(
                    f"{path.relative_to(root)}: dead wikilink [[{t}]]"
                )


def check_inbox(root: Path, warnings):
    inbox = root / "00_Inbox"
    if not inbox.is_dir():
        warnings.append("00_Inbox/ folder missing")
        return
    files = [f for f in inbox.iterdir() if f.is_file() and f.name != "_README.md"]
    if len(files) > 20:
        warnings.append(
            f"00_Inbox/ holds {len(files)} notes — schedule a sorting session"
        )


def main() -> int:
    root = find_vault_root()
    problems, warnings = [], []

    check_memory_md(root, problems, warnings)
    check_daily_notes(root, problems)
    notes = collect_vault_notes(root)
    check_wikilinks(root, notes, problems, warnings)
    check_inbox(root, warnings)

    score = max(0, 100 - len(problems) * 20 - min(len(warnings), 5) * 2)
    print(f"Verified Memory Vault — health check {datetime.now():%Y-%m-%d %H:%M}")
    print(f"Notes scanned: {len(notes)}")
    print(f"Health score: {score}/100")
    for p in problems:
        print(f"  PROBLEM: {p}")
    for w in warnings:
        print(f"  warn:    {w}")
    if not problems and not warnings:
        print("  All checks passed.")
    verdict = "HEALTHY" if not problems else "UNHEALTHY"
    print(f"Verdict: {verdict}")
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
