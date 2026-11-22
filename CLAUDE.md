# threads

CLI + Claude Code skill for GrepMem-style threads (append-only log, summary, regex recall). Built for a
restricted work machine. Read `GLOSSARY.md` for the terms and use them exactly; decisions are in
`docs/adr/`; notes, status and the interview record are on the vault hub `brain/projects/threads/`.

## Hard rules

- `thread.py` stays one file, Python standard library only, no network (ADR 0002). Target Python 3.9+.
- Thread data never goes into a repository (ADR 0001). Tests use `THREADS_HOME` in a temp directory.
- The log is append-only and stores transcript text uncut (`docs/LIMITS.md` lists the exceptions). Cap only what is printed, never what is stored.
- A hook must never fail a session: `thread hook` catches everything and writes `errors.log`. Exit code 2
  from a hook blocks the turn or the compaction in Claude Code, so nothing on the hook path may produce it.
- A feature on the "Not in v1" table in `docs/LIMITS.md` needs the owner's OK before it is built.
- The agent creates, opens, closes or reopens threads only when asked ("continue X" counts); hooks may inform, never bind.

## Run

- Tests (the only gate): `python3 -m unittest discover -s tests`
- Try it without touching real data: `env -u CLAUDE_CODE_SESSION_ID THREADS_HOME=/tmp/t python3 thread.py new "demo"`
  (without `env -u`, a run inside Claude Code binds the live session and copies its real transcript there).

## Layout

- `thread.py` the CLI; `tests/test_thread.py`; `skill/thread/SKILL.md` the skill; `hooks.json` the
  hooks to paste into `~/.claude/settings.json`; `docs/LOG.md` development log.
- When a command changes, update `README.md` and `skill/thread/SKILL.md` in the same commit.
