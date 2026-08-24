# tools/ — Self-check and protection for this vault

Two small scripts, standard library only, no installation:

## memory_check.py — "Is my memory healthy?"

Run at any time (agents: run it at the start of a session):

    python3 tools/memory_check.py

It scans the vault and reports:

- MEMORY.md protocol violations (entries without a date, duplicates,
  over the ~100-line budget)
- daily notes with names that are not `YYYY-MM-DD.md`
- dead wikilinks (Obsidian basename rule, `[[Target|Alias]]` and
  `[[Target#Anchor]]` handled)
- empty or unreadable files
- inbox pressure (more than 20 unsorted notes)

Exit code 0 = healthy, 1 = problems found — so agents and CI can act on it.

## memory_guard.py — "Don't let anyone wipe the memory"

The documented failure mode of agent memories: an agent cleans up a branch
and deletes its own brain. This guard makes that a refused commit instead.

Install (once, inside the vault's git repo):

    git init                 # if not already a repo
    ln -s ../../tools/memory_guard.py .git/hooks/pre-commit

or on systems without symlink support:

    cp tools/memory_guard.py .git/hooks/pre-commit

From then on every commit is checked before it lands:

- mass deletion of memory files (>3 in one commit) is refused
- removing lines from MEMORY.md without moving them to
  MEMORY-Archive.md in the same commit is refused
- intentional exceptions: `git commit --no-verify`

Both scripts need only Python 3.8+ and git. No plugins, no network,
no dependencies.
