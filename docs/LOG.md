# Log

## Rig usage

| Date | Machine | What |
|---|---|---|
| 2026-11-21 | Mac | Design interview, v1 build, tests. No model host, no satellites. |

## Development

- 2026-11-21: Design settled in three interview passes (grill-me, grill-with-docs, grill-me). v1 built:
  `thread.py`, tests, skill, hooks snippet, glossary, ADR 0001 and 0002.
- 2026-11-22: Two fresh subagents reviewed commit 5939282 (one on code, one on docs, skill and hooks).
  Fixed all verified findings: grep page cap hid matches; one unreadable transcript line stopped capture;
  stdio forced to UTF-8; closed or removed threads no longer receive capture; `~/.threads` and
  `errors.log` modes; note text parsed as flags; unique temp file names; `grep` captures first; install
  steps. Tests 5 -> 9, green on Python 3.14.7 and 3.9.6. `hooks.json` was checked against the official
  hooks documentation and left unchanged. Open, unverified: behaviour on Windows (README section).
- 2026-11-22: Second review by two fresh subagents at ae5c8a8. Owner decisions: the output of
  `thread grep` is not stored (the call is); a closed thread accepts notes only. Fixed: grep paging
  when its own calls are captured (active thread searched last, capture only on page 1); forked
  sessions re-capturing parent history; stale binding after a close elsewhere; reopen capturing the
  closed span; capture failure losing a note; corrupt state/meta crashes; invalid-JSON lines now
  recorded; home directory mode; SessionEnd timeout 10 s; install check redone so it fails without
  hooks. Tests 9 -> 17, including the hook and CLI as subprocesses. A reviewer's mutation run had
  22 of 26 mutants survive the 9-test suite; not re-run against the new suite.
- 2026-11-22: Third review by two fresh subagents at 0d17324; no high-severity finding. Owner decision:
  lines Claude Code injects (`isMeta`) are not captured. Fixed: grep-call detection limited to command
  position; `--all` back to id order, with earlier grep calls left out of searches (so paging cannot
  feed itself); bindings carry the thread's generation (uid + close count), so close+reopen or
  remove+recreate elsewhere detaches; no-text commands stop after 5 s on an open pipe; wrong-shape
  state/meta files; summary cut marker; Windows wrapper must not exit 2. Tests 17 -> 25.
  Own mutation check (150 single-token mutants, script not kept in the repo): 110 killed; of the 40
  survivors most change only message text or nothing observable. Known untested: the 5 s stdin wait
  (checked by hand), `grep --all` over a thread with no log file.

## Research notes

- Source: arXiv 2611.25123, "Forget Freely, Grep Later" (GrepMem). Taken from it: append-only log
  written by the harness, a summary that is also appended to the log, regex recall with pagination,
  count mode, context lines 1 (max 3), 10 matches per page (max 30), output cap about 6K characters,
  re-injection of the summary after compaction.
- Not from the paper (our own design): threads, kinds, open/closed, binding sessions to threads,
  backfill, notes, export.
- Read only through a fetch agent; the grep parameter defaults come from a model-written summary of
  the second half of the paper and were not checked against the PDF.
- Claude Code facts used: `CLAUDE_CODE_SESSION_ID` is set for Bash, PowerShell and hook commands (documented on the env-vars
  page; changes on `/clear`);
  transcripts are `~/.claude/projects/<dir>/<session>.jsonl` with `type` user/assistant and
  `message.content` blocks (text, thinking, tool_use, tool_result).
