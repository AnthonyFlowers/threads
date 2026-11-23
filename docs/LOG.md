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
- 2026-11-22: Methods compared with the paper by two subagents (the owner does not want strict
  conformance). Mechanism review: keep ours for always-available grep, the manual checkpoint,
  timestamps, `--type`, `--all`, no timeout. Hands-on test, 41 recall questions over four real
  transcripts, same regex for both greps: answer on page 1 for 27 (ours) against 21 (the paper's
  reference grep on a paper-format log); never found within 5 pages 7 against 14. Eight of the
  paper's misses were answers that exist only in tool-call input; newest-first alone moved five
  questions from page 3 to page 1. The questions were written with the logs in view, single sessions.
  - Borrowed from the paper: matches grouped under their entry in line order with merged context;
    the producing call shown on a result's header; counts broken down by entry type and by thread.
  - Owner decisions: subagent reports are captured (entry type `subagent`); Claude Code's
    compaction summary is logged (entry type `compaction`).
  - Fixed: reports were dropped by the injected-line rule; the own-grep rule hid Write calls and
    heredocs that only mention `thread grep`; replayed transcript lines were stored twice;
    background shell notices were labelled `subagent` (now `notification`). Added `--oldest`.
    Tests 27 -> 28.
- 2026-11-22: Fourth review (two fresh subagents, commits 5b53833..f22fb19). Fixed:
  - Messages delivered while a turn runs (queued attachments) were dropped unless they were agent
    reports: the user's own mid-turn messages (35 of 41 in the owner's transcripts existed nowhere
    else) and 725 of 822 subagent and shell notices. All queued messages are now captured. (The text
    match added with it, to merge a queued copy with its user line, was removed in the next entry.)
  - Folder reminder used a string prefix (`/work/app2` matched `/work/app`); now a path test on
    real paths, and a thread started in a root folder is left out.
  - Own-grep rule: quoted mentions no longer count; `rtk`, `env`, loops, `xargs` and `command` as a
    later key are recognised; calls without an id no longer hide each other.
  - Also: unknown `--type` is an error; control characters in headers are not printed; a fork drops
    parent lines of the fork's own second; short writes are completed; Windows error reporting.
  - **Mistake recorded:** an earlier mutation check (22 Nov, 13:11-13:21) wrote 148 test threads
    into the real `~/.threads`, because some mutants disabled the `THREADS_HOME` lookup. The owner
    had it deleted. The tests now also point `HOME` and `USERPROFILE` at their temp folder, so the
    code under test cannot reach the real home even when that lookup is broken.
  - Tests 28 -> 29.
- 2026-11-22: Blind review (two fresh subagents given only the repository path). Both found that the
  text de-duplication added in 603ff83 dropped real messages: a queued "ok" made every later "ok"
  vanish, and on the owner's recent transcripts it removed 119 entries, 1 of them a true duplicate.
  Owner decision: no de-duplication by text at all; a message that arrives queued and as a user
  line is logged twice. Also fixed: `open` with no transcript in reach could later capture the
  earlier session; escape sequences in titles and exported notes; a corrupt `meta.json` gave a
  traceback; an existing `THREADS_HOME` folder was set to mode 0700; an empty hook stdin wrote an
  error. Tests 29 -> 30.
- 2026-11-22: Review of 93a553c (two fresh subagents, one blind). No high-severity finding.
  - Owner decision: a per-session lock for capture, stale after 5 seconds. A waiting command does
    not skip; it waits for the lock to be released or to go stale. Eight parallel `thread note`
    calls after 200 new transcript lines now store each line once (400 copies before).
  - Completed fixes that fell short in 93a553c: `~/.threads` is always set to 0700 again (only an
    existing `THREADS_HOME` folder keeps its mode); `--kind`, the exported summary and all printed
    headers are stripped of control characters, now including C1 codes and bidi overrides; a
    `meta.json` of the wrong shape or encoding gives a message; `open` keeps lines of its own second.
  - New: a command in a session whose thread was closed or removed elsewhere says so. A captured line
    that would look like a header once printed is indented. Ids no longer end in `-`. The hook
    accepts a byte-order mark. The own-grep rule knows `timeout`, `{`, `!` and `/usr/bin/env`.
  - Tests 30 -> 32.

## Research notes

- Source: arXiv 2611.25123v1, "Forget Freely, Grep Later" (GrepMem). Taken from it: append-only log
  written by the harness, a summary that is also appended to the log, case-insensitive regex recall
  over log lines, 10 matches per page (max 30), 1 context line (max 3), count mode, each
  response capped at 6K characters and ending at a whole match with the offset for the next page,
  context kept inside one record and merged where it overlaps, matches grouped under their record's
  header and labelled with the call that produced them, a count broken down by source, earlier grep output left out of searches, and a note after
  compaction that the history is searchable.
- Differs from the paper: the paper's summary is written by the model at every automatic compaction
  (threshold 28,672 of a 32,768-token window) under a fixed prompt (key findings with their sources;
  candidate answers and how well each is verified; resolved clues and approaches that did not work;
  next steps), and the context is reset to system prompt + task + that summary. Our checkpoint is
  manual, has its own template, and is what the hook re-injects, so it can be stale (the hook says how
  many entries are newer). The paper enables grep only after the first compaction; ours is always
  available. The paper lists matches oldest first; ours newest first (`--oldest` reverses). The paper searches
  only record text; ours also searches headers and tool-call inputs. The paper clips lines to 300
  characters (ours 400) and stops a search after 10 s (ours has no timeout). The 6,000-character limit on the re-injected
  summary is ours, not the paper's.
- The paper has no ablations. Its evidence is one RL-trained model (Qwen3.5-9B) on single-episode
  benchmarks; before RL, GrepMem scored 75.0 on ContextBench Log Triage against 95.3 after, and
  below summary-only SUPO on BCP-Multi (40.9 against 45.2) while far above it on exact recall (KV
  93.9 against 10.9). Table 3 gives no intervals.
- Checked 2026-11-22 against the full PDF (v1, 17 pages, appendices A-F) and the code at
  github.com/limenlp/GrepMem commit b7e3744: the grep defaults above are correct. The parameter names are in the paper's
  Appendix A; "Python re" appears only in the code. The reference code does not log the model's
  reasoning, cuts tool outputs at 40,000 characters before logging, does not log the system prompt
  (Algorithm 1 says it does), does not search record headers, applies the 10 s limit only when the
  `regex` package is installed, and keeps the log in memory for one episode. Our own design, not from the
  paper: threads, kinds, open/closed, binding sessions to threads, backfill, notes, export.
- Claude Code facts used: `CLAUDE_CODE_SESSION_ID` is set for Bash, PowerShell and hook commands (documented on the env-vars
  page; changes on `/clear`);
  transcripts are `~/.claude/projects/<dir>/<session>.jsonl` with `type` user/assistant and
  `message.content` blocks (text, thinking, tool_use, tool_result).
