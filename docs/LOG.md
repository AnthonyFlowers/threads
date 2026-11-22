# Log

## Rig usage

| Date | Machine | What |
|---|---|---|
| 2026-11-21 | Mac | Design interview, v1 build, tests. No model host, no satellites. |
| 2026-11-22 | nzxt (Windows side, `ssh desktop-win`) | Windows behaviour research and fix verification in a temp folder; nothing installed. |
| 2026-11-22 | Mac | 11 headless Claude Code runs (haiku, about $0.06) for live-session research. |

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
- 2026-11-22: Research by four subagents, then two overall reviews.
  - Live sessions (Claude Code 2.1.323, 11 headless runs, temporary settings): hooks fire with the
    expected fields; `CLAUDE_CODE_SESSION_ID` equals the hook's `session_id`; capture, compaction
    re-injection and the skill worked; resume keeps the id; `/clear` and forks get a new one. Found: a
    fork's transcript copies the parent's lines under the fork's id (duplicate on bind, open); Claude
    Code's compaction summary was captured as a `user` entry (fixed).
  - Windows 11, Python 3.10, PowerShell 5.1, Git Bash (the nzxt desktop, outside Claude Code). Found
    and fixed: parallel log appends lost data (now `FILE_APPEND_DATA`); `os.replace` failed while the
    target was open (now retried); no-text commands hung on an open pipe (now a 5 s limit there too).
    After the fixes: 26 tests pass there, 40 of 40 parallel 300 KB notes intact. README Windows
    section rewritten from the measurements (two wrappers, text on stdin in PowerShell).
  - Docs: `StopFailure` hook added; minimum Claude Code 2.1.132; managed-settings and trust notes.
  - Also changed: grep context stays inside the entry; control characters are removed from printed
    text; `note`, `new` and the compaction hook report staleness or rebinding; `checkpoint` writes the
    log before `summary.md`. hooks.json changed in this release (new `StopFailure` entry). Tests 25 -> 26.
- 2026-11-22: Owner decisions after the research round, all built:
  - A session-start hook line names the open threads of the folder when the session has none active
    (hooks.json: `SessionStart` now has no matcher; **merge hooks.json again**).
  - Only `thread new` backfills; `open` and `reopen` capture from that moment. A fork is marked at
    session start and `new` there captures only what the fork did.
  - Log format: a tool call is `key: value` lines, and call and result headers carry the call id.
    `thread grep` output is stored again and skipped at search time (replaces the earlier marker).
  - `thread grep --type`, newest match first, subagent results as entry type `subagent`.
  - Skill: "continue X" counts as asking to open; the agent may offer a thread once.
  - README shortened: limits and "Not in v1" moved to `docs/LIMITS.md`. Tests 26 -> 27.

## Research notes

- Source: arXiv 2611.25123v1, "Forget Freely, Grep Later" (GrepMem). Taken from it: append-only log
  written by the harness, a summary that is also appended to the log, case-insensitive regex recall
  over log lines, oldest first, 10 matches per page (max 30), 1 context line (max 3), count mode, each
  response capped at 6K characters and ending at a whole match with the offset for the next page,
  context kept inside one record, earlier grep output left out of searches, and a note after
  compaction that the history is searchable.
- Differs from the paper: the paper's summary is written by the model at every automatic compaction
  (threshold 28,672 of a 32,768-token window) under a fixed prompt (key findings with their sources;
  candidate answers and how well each is verified; resolved clues and approaches that did not work;
  next steps), and the context is reset to system prompt + task + that summary. Our checkpoint is
  manual, has its own template, and is what the hook re-injects, so it can be stale (the hook says how
  many entries are newer). The paper enables grep only after the first compaction; ours is always
  available. The paper clips lines to 300 characters (ours 400), stops a search after 10 s (ours has
  no timeout), starts every result with the match count by source, labels each match with its tool
  call and arguments, and merges overlapping context. The 6,000-character limit on the re-injected
  summary is ours, not the paper's.
- The paper has no ablations. Its evidence is one RL-trained model (Qwen3.5-9B) on single-episode
  benchmarks; before RL, GrepMem scored 75.0 on ContextBench Log Triage against 95.3 after.
- Checked 2026-11-22 against the full PDF (v1, 17 pages, appendices A-F) and the code at
  github.com/limenlp/GrepMem commit b7e3744: the grep defaults above are correct. The parameter names
  and "Python re" come from the code, not the paper. The reference code does not log the model's
  reasoning and cuts tool outputs at 40,000 characters before logging. Our own design, not from the
  paper: threads, kinds, open/closed, binding sessions to threads, backfill, notes, export.
- Claude Code facts used: `CLAUDE_CODE_SESSION_ID` is set for Bash, PowerShell and hook commands (documented on the env-vars
  page; changes on `/clear`);
  transcripts are `~/.claude/projects/<dir>/<session>.jsonl` with `type` user/assistant and
  `message.content` blocks (text, thinking, tool_use, tool_result).
