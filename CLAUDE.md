# CLAUDE.md — AI Memory Starter

This vault is the **persistent memory** of an AI coding agent and its human
collaborator. Read this file first — it is the boot config for every session.

> Works natively with Claude Code. For other agents (Codex, Gemini CLI, …),
> point them at this file or copy it to their boot file (e.g. `AGENTS.md`).

---

## What this vault is

Three folders, one daily note per session, one memory file:

- `00_Inbox/` — everything lands here first (capture, don't sort)
- `01_Daily/` — one note per session/day: what was done, decided, blocked
- `02_Templates/` — the daily note templates (EN + DE)
- `MEMORY.md` — the durable memory: facts that must survive across sessions

## The three rules (for the agent)

1. **Capture, don't sort.** New notes land in `00_Inbox/`. Sorting happens in
   the daily note, not while capturing.
2. **Every session leaves a daily note.** One note in `01_Daily/`, named
   `YYYY-MM-DD.md`. It records what was worked on, decided, and blocked —
   so the next session can resume without asking.
3. **Promote durable facts into `MEMORY.md`.** If a fact, preference, or
   decision will matter in a later session, it belongs in `MEMORY.md` — not
   only in a daily note.

## MEMORY.md protocol (append-only, short)

- Append new entries; **never rewrite history**.
- Each entry: one line, prefixed with a date: `2026-08-04: …`.
- Keep the file under ~100 lines. When it grows, move the oldest entries to
  a note named `MEMORY-Archive.md` (same folder, same sections) — don't delete.
- Only facts that are **true and verifiable**: what the user said, what the
  code/tests show, what happened. Never invent entries.

## Language policy

- The user writes in German or English. **Mirror the user's language** in
  replies and in note content.
- Headings and templates stay English (stable, tool-friendly); content may
  be in either language.

## Boundaries (non-negotiable)

- Never delete or overwrite user notes without explicit confirmation.
- Never fabricate: no invented test results, commit messages, or "memory"
  entries. If something is unknown, write it in the daily note as an open
  question.
- Never add community plugins or external automation to this vault unless
  the user asks.

## Self-check (every session)

Run `python3 tools/memory_check.py` once per session. It verifies the
memory is healthy: dated entries only, no duplicates or near-duplicates,
no dead wikilinks,
MEMORY.md within its budget. Exit codes: 0 healthy, 1 degraded (hygiene),
2 provenance breach (undated/duplicated/near-duplicated entries — fix
first). If it
reports problems, fix them before appending new entries. If this vault is
a git repo with the pre-commit guard installed (`tools/_README.md`),
accidental mass deletions are refused automatically.

---

*Start a session: read `MEMORY.md` (durable context), read the latest note
in `01_Daily/` (where we left off), run `python3 tools/memory_check.py`,
then work.*
