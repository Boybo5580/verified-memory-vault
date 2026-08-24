# MEMORY.md — Durable Memory

> This file is the **long-term memory** of this vault. The agent reads it at
> the start of every session; the agent appends to it whenever a durable fact
> surfaces. Keep it short, append-only, dated.
>
> Rule: one line per entry, prefixed with a date. Under ~100 lines. When it
> grows, move the oldest entries to `MEMORY-Archive.md` (don't delete).
>
> Run `python3 tools/memory_check.py` to verify this memory is healthy.

## Project

- (one line: what are we building / working on right now)

## Preferences

- (how the user likes to work: language, tools, style, pace)

## Decisions

- (dated decisions that must not be re-litigated every session)

## Lessons

- (what we learned the hard way — one line each)

## Open Questions

- (things we don't know yet; the agent may answer them with evidence)

---

*Example entries (replace with your own):*

```markdown
## Project
- 2026-08-04: Building a small SaaS landing page; live at example.com; repo: github.com/me/project

## Preferences
- 2026-08-01: User writes in German, expects answers in German
- 2026-08-01: Prefers boring, well-tested solutions over clever ones

## Decisions
- 2026-08-04: Use SQLite instead of Postgres (simplicity, single-user)
- 2026-08-04: German is the primary language of the product

## Lessons
- 2026-08-03: A config change without a test broke staging for 2 hours — test first

## Open Questions
- 2026-08-02: Do we need auth for v1? (no users yet — revisit at first signup)
```
