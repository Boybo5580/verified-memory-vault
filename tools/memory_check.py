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

Risk classes / exit codes:
  0  HEALTHY            no defects
  1  DEGRADED           hygiene defects (dead links, naming, budget…)
  2  PROVENANCE BREACH  undated, duplicated, or near-duplicated memory
                        entries — the memory can no longer be trusted about
                        *when* something was learned; treat as strictly
                        worse than hygiene.

Provenance defects are the stricter class because every downstream consumer
(session boot, CI, shutdown hooks) relies on dated, non-duplicated entries;
a dead link is visible, silent provenance rot is not.

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


STOPWORDS = frozenset("""
a an and are as at be by for from has have in is it its of on or that the
this to we than rather was were will with would you your our their
""".split())


def _normalize_entry(text: str) -> str:
    """Entry text reduced for duplicate comparison: date stripped, lowercased,
    punctuation collapsed to spaces, stopwords dropped, tokens sorted.
    Byte-identical rewordings and same-fact entries with different dates both
    collapse to the same key."""
    t = re.sub(r"^\d{4}-\d{2}-\d{2}:\s*", "", text).strip().lower()
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return " ".join(sorted(w for w in t.split() if w not in STOPWORDS))


def check_memory_md(root: Path, problems, warnings, provenance):
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
        provenance.append(
            f"{len(bad)} MEMORY.md entry line(s) without a date "
            f"(format 'YYYY-MM-DD: fact'), e.g. {bad[0]!r}"
        )
    seen, dups = {}, []
    for ln in body:
        if not _is_entry_line(ln):
            continue
        key = _normalize_entry(_entry_text(ln))
        if key and key in seen:
            dups.append(ln[:60])
        elif key:
            seen[key] = ln
    if dups:
        provenance.append(f"{len(dups)} duplicate MEMORY.md entr(ies), e.g. {dups[0]!r}")
    # Near-duplicates: same fact re-captured across sessions in different or
    # extended wording (e.g. a port/fact entry repeated later with one detail
    # added). Exact-match dedup misses these because date/wording differ;
    # token overlap on normalized text catches them. Fires only when one
    # entry's tokens are nearly *contained* in the other's (containment) AND
    # overall overlap is substantial (Jaccard) — this separates "same fact,
    # more detail" from merely similar-looking distinct facts. Heavy
    # paraphrases with few shared content words remain undetected (stdlib-
    # only scope); they are a known limitation, not a false-positive risk.
    keys = [(key.split(), ln) for key, ln in seen.items() if len(key.split()) >= 3]
    near_dups = []
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            ka, la = keys[i]
            kb, lb = keys[j]
            sa, sb = set(ka), set(kb)
            inter = len(sa & sb)
            containment = inter / max(min(len(sa), len(sb)), 1)
            jaccard = inter / max(len(sa | sb), 1)
            if containment >= 0.8 and jaccard >= 0.55:
                near_dups.append((la[:60], lb[:60]))
    if near_dups:
        provenance.append(
            f"{len(near_dups)} near-duplicate MEMORY.md entr(ies) "
            f"(token containment >= 80%), "
            f"e.g. {near_dups[0][0]!r} vs {near_dups[0][1]!r}"
        )


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
    problems, warnings, provenance = [], [], []

    check_memory_md(root, problems, warnings, provenance)
    check_daily_notes(root, problems)
    notes = collect_vault_notes(root)
    check_wikilinks(root, notes, problems, warnings)
    check_inbox(root, warnings)

    score = max(0, 100 - (len(problems) + len(provenance)) * 20
                - min(len(warnings), 5) * 2)
    print(f"Verified Memory Vault — health check {datetime.now():%Y-%m-%d %H:%M}")
    print(f"Notes scanned: {len(notes)}")
    print(f"Health score: {score}/100")
    for p in provenance:
        print(f"  PROVENANCE BREACH: {p}")
    for p in problems:
        print(f"  PROBLEM: {p}")
    for w in warnings:
        print(f"  warn:    {w}")
    if not problems and not warnings and not provenance:
        print("  All checks passed.")
    if provenance:
        verdict = "PROVENANCE BREACH"
        code = 2
    elif problems:
        verdict = "UNHEALTHY"
        code = 1
    else:
        verdict = "HEALTHY"
        code = 0
    print(f"Verdict: {verdict} (exit code {code})")
    # Exit-code contract (risk classes):
    #   0 = HEALTHY            no defects at all
    #   1 = DEGRADED           hygiene defects only (dead links, naming, …)
    #   2 = PROVENANCE BREACH  undated/duplicated/near-duplicated memory
    #                          entries — stricter, because the memory can no
    #                          longer be trusted about when facts were learned.
    return 2 if provenance else (1 if problems else 0)


if __name__ == "__main__":
    sys.exit(main())
