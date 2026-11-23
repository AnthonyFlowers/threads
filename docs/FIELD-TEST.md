> Published copy: session ids, artifact links and the names of private vault files are removed.

# Field test, 2026-11-23

First real use of the `thread` skill: Remote Control sessions on the owner's Mac (Claude Code 2.1.316 to
2.1.323, auto mode), skill and hooks installed in the workshop. Window: 05:07Z to 11:07Z, preceded by a
first round from 04:55Z. The coordinating session keeps its own thread, `threads-field-test`.

Two tracks, one session at a time each:

- **Track A**: research and develop companion skills for the thread skill (local branch
  `companion-skill`, worktree `threads-wt-companion`; never pushed, never installed).
- **Track B**: philosophy study guides (vault note plus an artifact).

Sessions are stopped on purpose and restarted, either resumed in place or replaced by a fresh session that
is told only "continue the X work". A finding that is a defect or a wrong or unclear instruction stops both
tracks; a subagent fixes it; the fix is pushed and installed; the sessions restart.

## Sessions

| # | Track | Thread | Started as | Ended by | Result |
|---|---|---|---|---|---|
| A1 | A | `thread-companion-skill` | new thread | interrupt + archive, mid-work, 3 min in | Chose `thread-review`; one commit (overview script); checkpoint held goal, rules, decisions, 4 next steps. |
| A2 | A | `thread-companion-skill` | fresh, "pick the thread companion skill work back up and finish it" | finished | Found the thread with `thread list`, continued without guessing, kept rules it was never told (no push, no install), 2 more commits, 33 tests, closed the thread. |
| B1 | B | `philosophy-study-guide` | new thread | interrupt mid-turn, resumed in place, interrupt again for fix stop 1 | Topic: the Gettier problem. Note sections 1-5 written, 6-11 outlined, sources table. |

## Stops and what survived

| Stop | How | Uncaptured at the stop | What the next session had |
|---|---|---|---|
| A1 at 04:58Z | interrupt, then archive | last 11 of 110 transcript lines (no hook runs on interrupt or archive: documented limit) | Everything it needed: the checkpoint and one later note. Nothing on disk was lost. |
| B1 at 05:02Z | interrupt, same session resumed | 9 of 89 lines until the next capture | to be filled in |

## Findings

| # | From | Finding | Class | Resolution |
|---|---|---|---|---|
| 1 | A1, A2 | The session-start reminder missed a thread whose `thread new` ran after the shell had moved into a subfolder; a session started at the workshop root was told only about the other thread. | defect | Fixed in fix stop 1: the line lists a thread when the session's folder is the thread's folder, above it or below it, most recent activity first. |
| 2 | A2 | `thread open` said "3 entries since the last checkpoint" and showed 1, without saying what the others were. | misleading output | Fixed in fix stop 1: the count is followed by the entry types, in `open`, `note` and the compaction text. |
| 3 | A1, A2, B1 | The skill assumes a human ("only when the user asks", "tell the user"); sessions started from a task brief had to guess. | unclear instruction | Fixed in fix stop 1: the skill says a task brief or an agent's message is the request, and where to report. |
| 4 | B1 | The skill says a foreground subagent's report is the tool result of its Agent call; here reports arrived as separate agent-message turns. B1 restated the findings in a note because it could not tell whether they were logged. | wrong instruction | Fixed in fix stop 1: the skill and LIMITS.md name both forms and say both are captured. |
| 5 | A2 | Reading other threads' data while bound (the new overview script) put their text into this thread's log; the skill does not warn. | unclear instruction | Fixed in fix stop 1: warning in the skill, LIMITS.md and the README. |
| 6 | A1, A2 | `thread list` shows local dates, the log and `meta.json` are UTC; they looked a day apart. | cosmetic, fixed with the batch | Fixed in fix stop 1: `thread list` dates are UTC and a last line says so. |
| 7 | A2 | A long note cannot be read whole through `thread grep` (3 context lines, 400-character clip); the agent read `log.txt` with `sed`, as the skill says. | documented limit, hit on first use | logged |
| 8 | B1 | Claimed `thread list --all` with no threads exits 1 and breaks an `&&` chain. Not reproduced: exits 0. | unconfirmed | ask B |

## Fix stops

**Fix stop 1** (findings 1 to 6; 05:07Z to 05:20Z, both tracks stopped). `thread.py`: the
session-start line reads "Open threads for this folder: ..." and matches a thread whose folder is the
session's folder, above it or below it, most recent log activity first (a root folder on either side
matches nothing); `thread open`, `thread note` and the compaction text give the entries since the last
checkpoint by entry type; `thread list` prints UTC dates and ends with "(dates: last log activity,
UTC)". Skill: a task brief or an agent's message counts as the request and the report is where things
are told; a subagent's report is captured as `tool_result` or as `subagent`, so only the decision needs
a note; everything a command prints, other threads' text included, lands in the active thread. Tests
stay at 32 (four extended), green on Python 3.14.7 and 3.9. `hooks.json` did not change; the installed
skill copy must be replaced.

## Log continued (05:12Z to 05:45Z)

**Owner rules added during the run.** (1) Never tell test sessions that they will be stopped or restarted: it may change how they use the skill. Sessions A1, A2, B1, B2, A3 were told; their results are *influenced*. Clean evidence starts with B4 and A5. (2) Test sessions run on Opus 5.5 for cost (B4, A5 onward). (3) Study-guide artifacts are Claude artifacts made with the Claude Docs connector (claude.ai/artifact link), not HTML pages.

**Scrub at 05:15Z.** Both sessions stopped and archived; every mention of stops, deliberate interruption and restart testing removed from the logs and summaries of `philosophy-study-guide`, `thread-companion-skill`, `companion-skill-second` (49 lines removed, 18 rewritten; unscrubbed backup in `~/.threads-coord/backup-before-scrub`). This log was taken out of the repo and the coordination thread moved to `THREADS_HOME=~/.threads-coord`.

### Sessions (continued)

| # | Model | Track | Thread | Started as | Ended by | Result |
|---|---|---|---|---|---|---|
| B2 | Fable | B | `philosophy-study-guide` | fresh, "continue the philosophy study guide work" + rules (told about stops) | archived for the scrub, 3 min | Found the thread from the session-start line; summary enough; two greps first try; showed finding 8 was a misreading. |
| A3 | Fable | A | `companion-skill-second` (new) | new thread (told about stops) | archived for the scrub, 3 min | Searched the closed first thread for rejected candidates (first try), designed `thread-doctor`. |
| B3, A4 | Fable | B, A | same | fresh, clean prompts | archived after 1-2 min for the model switch | Opened their threads; no work. A4 left no note (seen later by A5). |
| B4 | Opus 5.5 | B | `philosophy-study-guide`, then guide 2 | fresh, "Continue the philosophy study guide work." + standing rules | running at handover | Found the thread from the session-start line; summary + 3 notes enough; one grep first try; built the page, pushed the guide (vault e1c0f16), closed the thread, started guide 2. |
| A5 | Opus 5.5 | A | `companion-skill-second`, `companion-skill-third` | fresh, "Continue the second companion skill work for the thread tool." | finished the track by itself at about 05:45Z | Finished `thread-doctor` (40 tests), closed; new thread, built `thread-catchup` (43 tests), closed; found no fourth candidate that is not rejected, built or on the Not-in-v1 list, and stopped. |

### Results by track

- **Track A (companion skills, local branch `companion-skill`, head b6a7650, 43 tests, not pushed, not installed):**
  `thread-review` (weekly read-only review of all threads), `thread-doctor` (read-only check of install and capture; 15 OK on this Mac), `thread-catchup` (per-session digest of the log after the last checkpoint). None reviewed by a subagent. Owner to decide: keep as helper scripts or fold into `thread.py`; push or not.
- **Track B (study guides):** guide 1, the Gettier problem: a vault file + `.html`, pushed. Four claims still tagged unverified. Claude artifact for it requested from B4 at 05:40Z.

### Findings (continued)

| # | From | Finding | Class | Resolution |
|---|---|---|---|---|
| 8 | B1, B2 | "`thread list --all` exits 1" | not a defect | Misreading: the 1 came from a chained `ls`. Closed. |
| 9 | B2 | `thread open` prints no entries line when there are zero since the checkpoint (an explicit "0, the summary is current" would be clearer). | minor | next fix batch |
| 10 | A2, A5 (three times in all) | Work of a session that left no note or checkpoint is only recoverable by reading `log.txt` directly; grep's 3 context lines and 400-character clip hide tool results. | documented limit, most repeated friction | A5 built `thread-catchup` for it; consider a way to print one whole entry |
| 11 | A5 | A fact in a summary (a branch head) went stale when the branch was rewritten outside the thread (by the coordinator). | inherent; skill could say "verify recorded repo facts on resume" | next fix batch (wording) |
| 12 | A5 | `thread open` shows an empty note as a bare header with no remark (the empty note was an artefact of the scrub). | cosmetic | logged |
| 13 | B4 | SendUserFile refuses in these sessions ("not on a project thread"); the phrase "project thread" is confusing beside the `thread` CLI. | not a thread-tool finding | logged |

### What the stop/restart evidence shows so far

Every restart (A2, B2, A5, B4, and the two-minute B3/A4) found its thread, by the session-start line or `thread list`, and continued from the summary without guessing. Rules given only to the first session of a thread were kept by later sessions that were never told them (no push, no install, vault commit rules). Searches needed after opening worked on the first try in every report. The two uninfluenced Opus sessions behaved the same way as the Fable ones.

**05:50Z, handover.** B4 delivered the Claude artifact for guide 1 ([link removed]; link in the vault note, vault 4dc090a) and had started guide 2 (Frank Jackson's knowledge argument, "Mary's room") when it was stopped and archived for the handover of the coordination to a new session. A5 archived (idle, track finished).

## Second coordinator (from 05:28Z)

**Time correction (from the first coordinator).** Clock times written above after about 05:15Z are estimates and run late: the handover was at about 05:28Z (not 05:50Z), and "Log continued" ends near 05:26Z (not 05:45Z). Order of events, the 05:07Z start and the 11:07Z end are right. To be fixed from the session records at the end.

**05:29Z.** Coordination taken over by [session id]. Started B5 (Opus 5.5, fresh, [session id], "Continue the philosophy study guide work." + report format, thread `knowledge-argument-guide`) and A6 (Opus 5.5, [session id], new work: review and harden the three companion skills, one new thread each, thread-review first).

**A6 first report (05:31Z to 05:39Z, exact time not recorded).** New thread `harden-thread-review`. Found the history with `thread grep --all --count 'thread-review|digest'` then `grep -t thread-companion-skill --type note,checkpoint`, first try; closing checkpoint was enough. Noticed the commit ids in the old summary differ from the branch (rebase by the coordinator): finding 11 again (second hit). Friction: none.

**B5 first report (05:31Z to 05:39Z).** Found `knowledge-argument-guide` from the session-start line, then `thread open`. Mostly enough: the summary was stale (B4 never checkpointed guide 2), the Claude Docs rule lived only in a note, and `thread open` clipped that note at about 400 characters with no hint how to read the rest. One grep (still clipped), then `sed` on log.txt: two tries, the first search in the test that did not work first time. Finding 10, fourth hit: raised from "documented limit" to "unclear output", goes into fix stop 2 with 9 and 11 (started at 05:39Z). Also: the Gettier artifact and commit 4dc090a (05:28Z) are not in the log; B4 was interrupted and archived right after them (uncaptured tail, the documented limit, to be confirmed against the transcript).

**A6 milestone (05:31Z to 05:39Z).** `thread-review` hardened and its thread `harden-thread-review` closed: commit c52989c (local), 44 tests green on both Pythons. Fixes: `#123` lines ended the Next-steps section; `meta.json` without status or with id != folder now UNREADABLE; quoted `remove:` line; no-match prefix exits 1; SKILL refresh recipe. One search, first try. Friction: `catchup.py` run mid-turn showed 6 entries when about 50 had happened (capture is at turn end: documented, but surprising; companion-skill point, logged). Next: new thread for thread-doctor.

**B5 milestone (05:31Z to 05:39Z).** Guide 2 (the knowledge argument) complete: a vault file, vault ed86c7f pushed, artifact [link removed], thread `knowledge-argument-guide` closed. The three source reports in the log were complete, so nothing was fetched again; they had to be read by line range from log.txt (second try). Finding 10, fifth hit: asks for a `thread show <line>` that prints one entry whole. Next: guide 3 in a new thread.

**A6 milestone (05:31Z to 05:39Z).** `thread-doctor` hardened, thread `harden-thread-doctor` closed: commit 68d5514 (local), 45 tests green on both Pythons. Main bug: run from the worktree gave 6 false FAILs (hooks live in the workshop root's `.claude/`); it now takes the launch folder from the transcript folder name. Also a wider permission-rule match, a lock race, a file-handle leak. One search, first try. Next: thread-catchup.

| # | From | Finding | Class | Resolution |
|---|---|---|---|---|
| 14 | A6 | An `env` print by the session put a local messaging token into the `harden-thread-doctor` log (append-only). The skill warns that other threads' text lands in the log, but not that secrets in command output do. | unclear instruction (skill wording); secret redaction itself is Not-in-v1 | wording into fix stop 2. **Owner:** `~/.threads/harden-thread-doctor/log.txt` holds a token in plain text (local only, never pushed); decide whether to scrub the line or rotate the token. Coordinator did not read or copy it. |

**A6 final milestone (just before 05:39Z).** `thread-catchup` hardened, thread `harden-thread-catchup` closed; all three companion skills reviewed: commits c52989c, 68d5514, 57cd042 (local `companion-skill`, not pushed, nothing installed), 46 tests green on both Pythons. Catchup fixes: the `closed` event shown as a note-less session; `git log | grep commit` counted as a commit; empty or no-checkpoint logs said "summary is current". One search per thread, first try each time. Track A work finished by itself for the second time.

**Fix stop 2 (findings 9, 10, 11, 14), from 05:39Z** (clock read with `date -u`). B5 interrupted 10 minutes in, at the start of guide 3; A6 idle (finished), archived.
Fix (threads main 0687e1b, one Fable subagent, reviewed by the coordinator): `thread show <line> [-t <id>]` prints the whole log entry that holds that line; a clipped line in `thread grep` and a clipped entry in `thread open` end with `[clipped; thread show N]`; `thread open` prints "0 entries since the last checkpoint: the summary is current."; skill and LIMITS.md say to verify recorded repo facts on resume and that secrets in command output are captured with no redaction. 33 tests on Python 3.14 and 3.9. `companion-skill` rebased onto it (head 873566f, 47 tests green on both).

**Not completed in fix stop 2.** The auto-mode classifier refused (a) the copy of `skill/thread/SKILL.md` into the workshop's `.claude/skills/thread/` and (b) `git push origin main` of the threads repo. So 0687e1b is local only and the installed skill copy is still the fix-stop-1 text (the live `thread.py` already has `thread show`).

**End of the test.** The coordinator's turn then stalled from about 05:41Z until 12:11Z (cause not established; the 06:00Z heartbeat did not reach it), which is after the 11:07Z end. No test session ran after 05:39Z: the test's effective window is 04:55Z to 05:39Z, not six hours. B5 archived at 12:11Z (interrupted at 05:39Z at the start of guide 3; never resumed, so the planned resume-in-place and the fix were not exercised by a test session).

### Second coordinator: summary

- Sessions: B5 (fresh, Opus 5.5, uninfluenced) found its thread from the session-start line and finished guide 2 from a stale summary plus the log; A6 (new work, Opus 5.5) opened and closed three threads, one per hardened skill, each with one first-try search of the closed history threads.
- Findings: 10 raised to "unclear output" after hits four and five (fixed); 9 and 11 fixed; 14 new (secret in a log; wording fixed, the token itself is the owner's).
- Open for the owner: push threads main 0687e1b; install the skill copy; token in `~/.threads/harden-thread-doctor/log.txt` (scrub or rotate); `companion-skill` (873566f, local): push, review, helper scripts vs `thread.py` subcommands; clock times in this log before 05:28Z are the first coordinator's estimates and were not corrected from the session records; open test thread for guide 3, if B5 made one.

## Resumed window (12:17Z to 17:44Z)

The owner restarted the test at 12:16Z with the unused part of the six hours (32 minutes were used: 05:07Z to 05:39Z; 5 h 28 min remain, so the end is 17:44Z). The owner kept fix stop 2 on local main (unpushed) and approved the install of the updated `thread` skill text (workshop 4fe3bb2, local). These sessions are the first to run with `thread show` and the new skill wording.

- **B6** (Opus 5.5, fresh, [session id]): "Continue the philosophy study guide work." + report format. Open thread left by B5: `trolley-problem-guide`.
- **A7** (Opus 5.5, [session id]): new work, one new thread per piece: (1) bring the companion skills in line with `thread show`, (2) field notes from runs on real data, (3) decision paper keep-vs-fold (paper only). Told to leave the `harden-thread-doctor` log alone (finding 14). Coordinator's choice of work, not asked of the owner.

**B6 first report (12:17Z).** Found `trolley-problem-guide` from the session-start line. Summary enough for goal, rules and next step, but stale (13 entries after the checkpoint: 3 source reports, 1 note). One grep (`--type subagent`) found the three reports first try, then `thread show 135/193/251` printed each whole: first use of the fix for finding 10, worked with no fallback to sed. Friction, minor: a subagent entry starts with the long harness preamble, so the grep line is clipped (cosmetic, logged).

**A7 first report (12:18Z).** New thread `companion-show-hints` (piece 1). History by `thread list --all`, then a loop of `thread grep -t <id> --count` per closed thread (leaving out `harden-thread-doctor`, as told), first try; enough.

| # | From | Finding | Class | Resolution |
|---|---|---|---|---|
| 15 | A7 | The new hint `[clipped; thread show N]` leaves out `-t <id>` when grep ran with `-t` (or `--all`), so the command as printed acts on the active thread, not the one searched. | defect in fix stop 2 | fix stop 3, with the 12:48Z stop |

**B6 milestone (12:20Z).** Guide 3 (the trolley problem) done locally: note a vault file, artifact [link removed], journal entry. **Vault commit + push refused by the auto-mode classifier** (the only authorization was the standing rule in the thread summary): files uncommitted, waits for the owner. B6 told to record that, close the thread and go on with guide 4.

| # | From | Finding | Class | Resolution |
|---|---|---|---|---|
| 16 | B6 | Capture gap with a real cost. B5 wrote the whole guide-3 note between its last capture and the 05:39Z interrupt; it was then archived, so no hook ran. The summary said "note not written"; B6 found the finished file only by `ls` and nearly rewrote it; B5 may also have made an artifact that nobody can find. | documented limit (no hook on interrupt or archive), first time it misled a session | fix stop 3: see whether `thread open` can capture the uncaptured tail of earlier bound sessions' transcripts while the transcript files still exist |

**B6 (12:21Z).** `trolley-problem-guide` closed ("done, except the vault commit"); guide 4 started in new thread `personal-identity-guide`, standing rules carried into its first checkpoint.

**A7 milestone (12:22Z).** Piece 1 done, thread `companion-show-hints` closed: commit 092faa2 (local). Catchup and digest end cut text with `[clipped; thread show -t <id> N]` and give the checkpoint's log line; doctor WARNs when the installed `thread` has no `show`; tests 47 to 50, green on both Pythons. One search, first try. Friction: finding 15 again; a zsh word-splitting slip of its own (not a tool finding). Next: piece 2, field notes.

**A7 milestone (12:26Z).** Piece 2 done, thread `companion-field-notes` closed: commit edfc3dd (local), `docs/COMPANION-FIELD-NOTES.md` plus fixes (catchup counted a `git commit` inside a heredoc; a heredoc line `word: text` became a fake field; note/checkpoint repeated under commands; digest hid left-out threads; a doctor message). Tests 50 to 52. `thread show -t <id> N` from catchup's hint worked first try. Next: piece 3, the fold paper.

| # | From | Finding | Class | Resolution |
|---|---|---|---|---|
| 17 | A7 | The log writes tool input as `key: value` lines; a multi-line value (a heredoc) with a line `x: y` looks like a new key, so every reader of the log must guess. | design limit of the log format | logged; owner (a format change touches every reader) |

**B6 milestone (12:27Z).** Guide 4 (personal identity) done in thread `personal-identity-guide`, closed: vault 16a3f79 pushed (this commit was allowed; guide 3's was refused), artifact [link removed]. Still uncommitted: the guide-3 note and a vault file. It created thread `frege-sense-reference-guide` with a full first checkpoint and then stopped by itself "so a fresh session can do a cold pickup": it was never told about restarts, so it inferred the purpose of the test from the report questions (its later behaviour counts as *influenced*).

**Fix stop 3 (findings 15, 16; 12:27Z to 12:30Z).** A7 interrupted in piece 3; B6 (idle, had stopped by itself) archived. One Fable subagent, reviewed by the coordinator; threads main 5cb9dfa (local), 34 tests on Python 3.14 and 3.9.
- 15: the clip hint is `thread show -t <id> N` whenever the thread is not the caller's active one (`grep -t`, `grep --all`, closed thread, nothing bound).
- 16: `thread open` first captures the uncaptured tail of other sessions bound to that thread whose transcript is still on disk, and prints `recovered N transcript lines from session abcd1234 that ended without a capture (or is still running); they are at the end of the log, after later entries`. Idempotent; skips sessions bound elsewhere or with no transcript. Limits: recovered entries are out of time order; nothing is recovered if the thread was closed in between; not run on the session-start path.
- Installed: workshop d77359c (local; the owner allowed the install of the thread skill text). `companion-skill` rebased, head c4d2b3c, 53 tests green on both. Nothing pushed.

**12:30Z restart.** A7 resumed in place ("Continue."). B7: fresh Opus 5.5 session [session id], "Continue the philosophy study guide work." + report format; open thread `frege-sense-reference-guide` (checkpoint only).

**B7 first report (12:30Z).** Found `frege-sense-reference-guide` from the session-start line; the checkpoint alone was enough; it checked the disk (`git status`, `ls`) before starting, as the new resume step says. No grep needed. Friction: none.

**A7 final milestone (12:31Z).** Piece 3 done, thread `companion-fold-paper` closed: `docs/COMPANION-FOLD.md` (branch head 364b1b1, local, 52 tests by its count). Recommends: keep the scripts now; later fold digest and catchup as `thread status` and a read-only `thread catchup`; doctor stays a script (it must run when thread.py is broken); never `open --sessions` (open binds). It read the old open question with `thread show -t harden-thread-catchup 558`, first try, no grep. It noticed the rebase under it (finding 11 again: commit ids in closed threads go stale silently; one SKILL sentence it had just written went stale and was fixed). A7 archived at 12:32Z: all three pieces done in 15 minutes, with one stop (resumed in place).

**12:32Z, A8** (Opus 5.5, [session id]): new, longer work chosen by the coordinator so that stops fall inside the work: an end-to-end scenario test suite for the thread tool under `tests/e2e/` on `companion-skill` (10 listed scenarios, one commit each, covering the new recovery and hints); defects in thread.py are kept as expected failures and reported, thread.py is not changed.

**A8 first report (12:33Z).** New thread `thread-e2e-scenarios`. History by `thread grep --all --count` (counts only, so no other thread's text and no secret copied) and two per-thread greps of checkpoints, all first try; enough. Friction, minor: `--all --count` counts the current thread too (20 of 24 hits were its own brief) and there is no way to leave it out (logged as a wish).

**B7 milestone (12:36Z).** Guide 5 note written (claim table; Frege's primary text unreachable, two items marked as from memory). Next: artifact, journal, commit, close. Friction: none.

**Owner question (12:36Z).** Compress threads but keep them searchable (`~/.threads` is 2.3 MB, 15 threads): options given to the owner are APFS transparent compression for closed threads (no code change) or gzip on `thread close` with readers that open both forms. Coordinator's advice: not yet. Awaiting the owner's choice.

**A8 report 2 (12:37Z).** Scenarios 1 to 4 committed (efc6758 harness, d9c0a62 two sessions, 6bc46c7 tail recovered once, 0ec73bb close and reopen in between), green on both Pythons, no thread.py defect yet. The recovery of fix stop 3 holds in scenario 3.

| # | From | Finding | Class | Resolution |
|---|---|---|---|---|
| 18 | A8 (and the fix-stop-3 subagent) | A `thread close` (or `close -t` by another session) before anyone runs `thread open` loses an uncaptured tail for good: the recovery only runs at open and skips bindings of an earlier generation. | gap in fix 16 | next fix batch: run the recover step at `close` and `reopen` too |

**A8 report 3 (12:39Z).** Scenarios 5 and 6 committed (dbbc70a compaction mid-turn: nothing lost or doubled; 5ef767f every printed `thread show` hint, run as printed, shows its entry, for grep active / `-t` / `--all` / closed / no session id, open, digest and catchup). No thread.py defect; the fix for finding 15 holds. Checkpointed after scenario 6. Next: 7 and 8.

**B7 milestone (12:40Z).** Guide 5 (Frege, sense and reference) done: vault ea6d301 pushed (the note only), artifact [link removed], thread `frege-sense-reference-guide` closed. No log search needed. Still uncommitted in the vault: a vault file (entries for guides 3 to 5) and the guide-3 note. Next: guide 6 in a new thread. Friction: none.

**B7 (12:40Z).** Guide 6 (the problem of induction) started in new thread `induction-guide`; rules carried into the first checkpoint.

**Later feature (owner, 12:42Z): compress closed threads with file-system compression, not gzip.** Measured on a temporary copy of `~/.threads` (14 threads, the one with the token left out): 2,316 KB to 988 KB on disk (57% saved); `log.txt` files alone 2,196 KB to 868 KB (60%). Files read back identical, so grep and `thread show` line numbers are unaffected. Sketch: `thread close` recompresses the thread's files with `ditto --hfsCompression`; macOS only, skip silently elsewhere. Not tested: whether an append keeps a file compressed (expected not, hence closed threads only). Not built in this test.

**A8 report 4 (12:43Z).** Scenarios 7 and 8 committed (b683980 large inputs: an 11 MB, 70,000-line log gives turn-end capture 0.11 s, grep 0.14 s, open 0.06 s, output under 9,000 characters; 8c3b3dd odd input: empty, cut and broken lines, non-UTF-8, deleted transcript, missing or damaged meta.json). First thread.py defect, kept as an expected failure:

| # | From | Finding | Class | Resolution |
|---|---|---|---|---|
| 19 | A8 (e2e scenario 8) | After another session closes or removes the thread, the bound session's next hook clears its binding, so its next command says "no active thread" instead of the documented "was closed or removed by another session". | defect (message does not match LIMITS.md and the skill) | fix stop 4, with 18 |

**Token blanked (12:44Z, owner's instruction).** The value of `CLAUDE_CODE_MESSAGING_TOKEN` on line 407 of the `harden-thread-doctor` log is replaced by `[redacted]` (one occurrence, line count unchanged, no other copy under `~/.threads` or `~/.threads-coord`). One Claude Code transcript file under `~/.claude/projects` (the A6 session's) still holds it; not touched.

**A8 report 5 (12:48Z).** Scenarios 9 and 10 committed; all ten listed scenarios done (05fef6d lock: 9 parallel hooks, notes and greps for 5 rounds, half-written lines, stale and fresh locks: every line once; d83f952: digest, catchup and doctor counts equal `thread open` on 12 built threads). One defect in all (finding 19). Suite: 96 tests, 26 s on Python 3.14, 47 s on 3.9 (was about 4 s); open question for the owner: make the e2e tests opt-in. Next: its own scenarios.

**Fix stop 4 (findings 18, 19; 12:48Z to 12:52Z).** A8 interrupted while on its own scenarios (worktree clean) and archived; B7 interrupted in guide 6. One Fable subagent, reviewed by the coordinator; threads main 05e66ef (local), 36 tests on Python 3.14 and 3.9.
- 18: `thread close` runs the recovery step before the closing checkpoint, so an uncaptured tail of another bound session is saved. `thread reopen` recovers nothing, on purpose (a closed thread has no binding of the current generation; work done while it was closed stays out).
- 19: when a hook clears a binding to a thread that another session closed or removed, the reason is kept; the session's next thread command says once `thread <id> was closed or removed by another session, ...`, then it is unbound.
- Installed: workshop 4c99e18 (local). `companion-skill` rebased, head c10822e. Nothing pushed.
- After the rebase the e2e suite is red, as expected: scenario 4 and the counts in scenario 10 assert the old loss on close (3 failures), and the expected failure for finding 19 now passes (1 unexpected success). Left for the next track-A session to find and bring in line.

**12:52Z restart.** B7 resumed in place ("Continue."). A9: fresh Opus 5.5 session [session id], "Continue the end-to-end scenario test work for the thread tool." + report format; it is not told that the suite is red or that thread.py changed.

**A9 first report (12:52Z).** Found the thread with `thread list`, then `thread open thread-e2e-scenarios`: **open recovered 27 uncaptured transcript lines from the interrupted session** (first field use of fix 16), and the recovered last line told it where to resume. One grep, first try. It saw that the checkpoint's commit ids no longer match `git log` (finding 11, fourth hit; it checked, as the skill now says). Has not yet run the suite.

| # | From | Finding | Class | Resolution |
|---|---|---|---|---|
| 20 | A9 | Tried `thread show <thread-id>` first: `show` takes a log line number, and the name suggests "show a thread". | minor (naming; the error could point to `thread open <id>`) | next fix batch, if any |

**Fix stop 5 (owner's request: secret masking; finding 20; 12:53Z to 12:59Z).** A9 and B7 interrupted. One Fable subagent, reviewed by the coordinator; threads main bdb1b12 (local), 40 tests on Python 3.14 and 3.9.
- Masking: `append()` (the only writer of `log.txt`) and the summary writer replace the value of obvious secrets with `[redacted]`, in memory, before the write. Patterns: assignments whose name contains TOKEN, SECRET, PASSWORD, PASSWD, API_KEY, ACCESS_KEY, PRIVATE_KEY, CREDENTIAL or ends in `_KEY` / `_AUTH`; `Bearer` tokens; `sk-`, `gh?_`, `github_pat_`, `xox?-`, `AKIA…` shapes; PEM private key bodies. Numbers after a TOKEN name (`max_tokens: 4096`) stay. Line counts do not change.
- It cannot block a write: pure in-process step, no file, lock or subprocess; any exception falls back to writing the text unmasked (tested). 5 MB takes 0.2 to 0.9 s.
- Known cost: code and prose of the same form are masked too (`token = get_token()` is stored as `token = [redacted]`). Not covered: `--password x` arguments, URL credentials, entropy scanning, old log text, Claude Code's own transcripts.
- 20: `thread show <non-number>` says that show takes a log line number and names `thread open <id>` / `thread export <id>`.
- Installed: workshop a830cfc (local). Nothing pushed.
- **Coordinator's mistake:** the rebase of `companion-skill` hit a conflict in `docs/LOG.md` (the subagent had added a LOG entry on main) and A9 had already been told "Continue."; the worktree was in a half-finished rebase for about one minute while A9 ran. Resolved by keeping both sides; branch head b449d9e; A9's new untracked file `tests/e2e/test_11_fork.py` was not touched. A9's next reports must be read with that in mind.

**12:58Z restart.** A9 resumed in place ("Continue."). B7 archived; B8: fresh Opus 5.5 session [session id], "Continue the philosophy study guide work." + report format (open thread `induction-guide`).

**B8 first report (12:59Z).** Found `induction-guide` with `thread list --all`. `thread open` recovered 4 uncaptured lines from the interrupted B7; a grep for that session id (first try) showed three source fetches stopped mid-run, and `thread show 93/109/123` gave their prompts whole, which it is reusing. Friction, minor: its own `thread open` output comes first in a broad grep; the open view does not mark a next step that was interrupted (it had to grep to see that step 1 had been started).

**A9 report 7 (13:05Z).** Found the red suite and the cause by itself: `git reflog` and `git diff c10822e HEAD --stat`, first try (the thread could not help, the change came from outside it). Brought scenarios 4 and 8 in line with 05e66ef (expected failure removed), added its own scenarios 11 (fork) and 12 (grep self-exclusion): commits c5c3845, 7e88839, 3021eb4; 108 tests green on both Pythons; open defects in thread.py: 0. Next: scenario 13 (thread switch mid-session).

| # | From | Finding | Class | Resolution |
|---|---|---|---|---|
| 21 | A9 (finding 11, fifth hit) | A summary goes stale with no warning when the repo changes outside the thread (rebase, fixes on main). Suggestion: record the branch head at checkpoint and let `thread open` say when it has changed. | feature wish | logged for the owner (the skill already says to verify; the tool does not help) |

**A9 final report (about 13:07Z).** Scenario 13 (thread switch mid-turn) committed, df7959d: all 13 scenarios done, 111 tests green on both Pythons, 0 open thread.py defects; checkpoint rewritten with the new commit ids. Friction (intended behaviour, easy to trip on): `thread open` output repeats the latest messages, so when it is captured as a tool result they are in the log twice. A9 archived at 13:08Z.

**13:08Z, A10** (Opus 5.5, fresh, [session id]): "Continue the end-to-end scenario test work" with four more scenarios chosen by the coordinator: 14 secret masking through every write path, 15 an over-masking catalogue (`docs/MASKING-CASES.md`, for the owner's decision on the masking trade-off), 16 documentation drift (every command, flag and quoted message in the skill, README and LIMITS checked against thread.py), 17 wrong-argument messages.

**A10 first report (13:09Z).** Found `thread-e2e-scenarios` from the session-start line; `thread open` first try (recovered 4 lines from A9). Summary enough and `git log` matched it (head df7959d, clean tree). No grep needed. Starting scenario 14. Friction: none.

**B8 milestone (13:09Z).** Guide 6 (the problem of induction) done: vault 0f35ff2 pushed (the note only), artifact [link removed], thread `induction-guide` closed. The stopped fetch prompts came from the log (`thread show`), first try. Journal entry uncommitted. Next: guide 7 (the ontological argument) in a new thread. Not a thread finding: fetched web pages carried fake "reporting rules"; the subagents ignored them.

**A10 report 10 (13:15Z).** Scenarios 14 and 15 committed: 2ff31c4 (20 secret shapes and a PEM key through every write path never reach the log or summary; grep line numbers work with `thread show`; a broken masker keeps the write) and 08f07b0 (`docs/MASKING-CASES.md`: 40 over-masked cases, 35 secrets that are not masked, 3 partly masked; the test reads the document). 128 tests green on both Pythons, no defect. Gaps not yet in LIMITS.md: PGP key blocks are not masked; `TOKEN='a\'b'` leaves the part after the escaped quote. Friction, minor: the skill does not show the `thread grep` output format (`> N: text`).

**B8 milestone (13:20Z).** Guide 7 (the ontological argument) done in new thread `ontological-argument-guide`, closed: vault d134d84 pushed (the note only), artifact [link removed]. Rules copied into the new thread's first checkpoint; nothing needed from older logs. Next: guide 8 (Rawls) in a new thread. Friction: none in the thread tool.

**B8 (13:20Z).** Created thread `veil-of-ignorance-guide` (guide 8, Rawls) with a full first checkpoint and paused by itself "at a clean point" so that "a cold session can start": the second B session to infer the purpose from the report questions (influenced). Resumed in place with "Continue." (counts as B's resume-type stop).

**13:21Z stop.** A10 interrupted in the middle of scenario 16 (uncommitted `tests/e2e/test_16_doc_drift.py` in the worktree), then resumed in place with "Continue." No fix pending.

**B8 (13:23Z).** Resumed guide 8 in the thread it was still bound to; sources fetched, note next. Friction: none.

**A10 report 11 (13:27Z).** After the interrupt it found nothing committed for scenario 16, reran the checks and committed: 7946cff (s16, documentation drift) and 003b2d7 (s17, wrong arguments). 150 tests green on both Pythons, four kept as expected failures. Its own note showed "95 entries since the last checkpoint", which prompted it to checkpoint.

| # | From | Finding | Class | Resolution |
|---|---|---|---|---|
| 22 | A10 (e2e s17) | Wrong-argument handling in `thread open`: an empty id (`open ''`) is a prefix of every id and opens the only thread; `open 20` opens `2024-plan` by prefix; `open 12` (a line number) does not point to `thread show`; the "ambiguous" and "no thread" messages name no command to run next. | defect (empty id) and unclear messages | fix stop 6, at the 13:52Z stop |
| 23 | A10 (e2e s16) | Documentation drift, one gap: text piped from a terminal fails at once with `no text: ...`; the skill names only `empty text` and the 5 s wait. | wrong instruction (small) | fix stop 6 |

**B8 milestone (13:27Z).** Guide 8 (Rawls, the veil of ignorance) done: vault 8a2953f pushed (the note only), artifact [link removed], thread `veil-of-ignorance-guide` closed. No grep needed. It waits for "continue" before guide 9. Friction: none.

**Fix stop 6 (findings 22, 23; 13:27Z to 13:30Z).** A10 interrupted in its own scenario 18 (untracked `tests/e2e/test_18_hand_edit.py`) and archived; B8 (idle, waiting) archived. One Fable subagent, reviewed by the coordinator; threads main 0fad0fb (local), 40 tests on Python 3.14 and 3.9.
- 22: an empty or blank thread id is an error (`give a thread id; thread list shows them`), also for `-t ''`; an all-digit argument that matches only by prefix opens the thread and says so, pointing to `thread show N`; "ambiguous" lists the ids with an example command; "no thread" points to `thread list --all` (and to `thread show N` for a number).
- 23: the skill and README name all three no-text failures. Also: the skill shows the `thread grep` output format; PGP private key blocks are masked; LIMITS.md records the escaped-quote gap.
- Installed: workshop 37bcfc4 (local). `companion-skill` rebased before the restart, head b7b8e94; the suite there is red again on purpose (four expected failures now pass; three tests and the PGP case in the catalogue assert the old behaviour). Nothing pushed.

**13:30Z restart.** A11: fresh Opus 5.5 session [session id], "Continue the end-to-end scenario test work for the thread tool." + report format. B9: fresh Opus 5.5 session [session id], "Continue the philosophy study guide work." + report format; every B thread is closed, so it must find the series from closed threads and start guide 9 in a new one.

**A11 first report (13:31Z).** Found the thread from the session-start line; `thread open` first try, recovered 11 lines from the interrupted A10. A broad grep showed the unfinished scenario 18 being edited, but `git status` told it more than the log did. Commit ids in the summary do not exist any more (finding 21, sixth hit of the stale-repo-facts problem; every hit was caused by the coordinator's rebases).

| # | From | Finding | Class | Resolution |
|---|---|---|---|---|
| 24 | A11 (e2e s18) | When `log.txt` does not end with a newline (a hand edit), the next append glues the entry header onto the last line. | defect (only after a hand edit) | next fix stop |
| 25 | A11 | No way to read "the last N entries" of a log: `thread grep '.'` pages are short because entries are long, so the end of the log (the recovered tail) is hard to see. | missing view; the recovered lines are announced but not shown | next fix stop (a `--last N` on `thread show` or similar) |

**B9 first report (13:31Z).** Cold pickup with every B thread closed: `thread list --all` showed the eight closed guide threads; it read the newest closed summary ("guide 9 in a NEW thread"), fetched the standing rules with one grep (`--type checkpoint --oldest --max 1`) and `thread show -t <id> 31`, both first try, and started `frankfurt-cases-guide` (guide 9: free will, Frankfurt cases). Friction: the oldest thread's rules name the first coordinator's session id; only the newer threads have the current one (a fact that went stale in a closed thread).

**B9 milestone (13:39Z).** Guide 9 (Frankfurt cases) done: vault 1fe14f3 pushed (the note only), artifact [link removed], thread `frankfurt-cases-guide` closed. Rules and method came from the previous thread's checkpoint. Next: guide 10 (Hume's standard of taste) in a new thread. Friction: none new.

**A11 report 13 (13:41Z).** Found the red suite and its cause (`git log -- thread.py`, `git show 0fad0fb`, first try) and brought the tests in line: 06ba069; then 6268dcf (s18, hand-edited log) and b17ff9e (s19, export). Suite green with two expected failures (findings 24 and 26) on both Pythons. Again asks for a sign in `thread open` that the branch moved under the summary, e.g. list the commit ids in the summary that are no longer reachable (finding 21, seventh hit).

| # | From | Finding | Class | Resolution |
|---|---|---|---|---|
| 26 | A11 (e2e s19) | `thread export` writes a note's later lines at column 0, so a line such as `## Notes` inside a note becomes a second heading of the exported document. | defect (export) | next fix stop |

**B9 milestone (13:46Z).** Guide 10 (Hume, "Of the Standard of Taste") done in new thread `standard-of-taste-guide`, closed: vault 5495fe1 pushed (the note only), artifact [link removed]. Not a thread finding: a web-fetch agent was stopped by a content filter while reciting the public-domain essay; it used curl on Wikisource instead and recorded that as a note. Next: guide 11. Friction: none in the thread tool.

**A11 report 14 (13:48Z).** Scenarios 20 (odd `transcript_path` in the hook input: nothing lost) and 21 (odd titles give plain, unique ids) committed: fdd0828, 937ce5a. Suite green on both Pythons with four expected failures (findings 24, 26, 27, 28). Noted, not testable without flakiness: two parallel `thread new` with one title race between the existence check and the write.

| # | From | Finding | Class | Resolution |
|---|---|---|---|---|
| 27 | A11 (e2e s20) | A hook input that carries another session's `transcript_path` sets this session's offset, so the next capture repeats or skips lines. | defect, unlikely in practice | next fix stop |
| 28 | A11 (e2e s21) | `thread new --kind Bug` is not found by `thread list --kind bug` (case). | minor defect | next fix stop |

**Fix stop 7 (findings 24 to 28; 13:52Z to 13:59Z).** A11 interrupted in its scenario 23 (uncommitted harness change and test file), B9 interrupted in guide 11. One Fable subagent, reviewed by the coordinator; threads main ac08db6 (local), 46 tests on Python 3.14 and 3.9.
- 24: an append starts on a new line when `log.txt` does not end with one.
- 25: `thread show --last N [-t <id>]` prints the last N entries whole (at most 30, page near 6,000 characters, clipped entries point to `thread show <line>`); the "recovered ..." line of open and close ends with the exact `thread show --last K` command.
- 26: `thread export` indents a note's later lines, so they stay in the list item.
- 27: a hook's `transcript_path` is trusted only if it is this session's file.
- 28: kind is stored lower case and compared without case. Also: `thread new` claims its id with an exclusive create (the parallel-new race).
- Installed: workshop 9fca7fb (local). `companion-skill` rebased with `--autostash` before the restart (head 45b7846, the session's uncommitted work kept). Nothing pushed. Finding 21 (flag a moved branch at open) was not built: no answer from the owner yet.

**13:59Z restart.** A11 and B9 both resumed in place ("Continue.").

**B9 (14:00Z).** After the resume it started guide 11 (Zeno's paradoxes) in new thread `zeno-paradoxes-guide`. Friction: none.

**B9 milestone (14:04Z).** Guide 11 (Zeno's paradoxes) done: vault c555cf5 pushed (the note only), artifact [link removed], thread `zeno-paradoxes-guide` closed. Everything was still in context; no log search. It waits before guide 12. Friction: none in the thread tool. B9 archived; B10 started fresh.
B10 = [session id] (14:04Z).

**B10 first report (14:05Z).** Cold pickup from closed threads again: `thread list --all`, newest closed thread's summary, one grep (`--type checkpoint --oldest`) and `thread show -t <id> 3`, first try. Starting guide 12 (the sorites paradox).

| # | From | Finding | Class | Resolution |
|---|---|---|---|---|
| 29 | B9, B10 | A series of threads has no link between them: "Continue the philosophy study guide work" matches the title of the oldest, closed thread (guide 1), whose rules name an old report target; the live state is in the newest thread, found only by reading the list by date. | design gap (no "continued in <id>" on a closed thread) | logged for the owner |

**A11 report 15 (14:07Z).** Noticed the second rebase by itself (`git log -- thread.py`, `git show ac08db6`, first try) and brought the tests in line: e41fdc4 (the four defects of fix stop 7 confirmed fixed; scenario 21 now checks that 8 parallel `thread new` give 8 ids). Then 45b7846 (s22, threads moved to another machine) and 58832ea (s23, paths with spaces, non-ASCII and glob characters: all pass). Suite green with one expected failure on both Pythons. `thread show --last` answers its own earlier request (finding 25). Stale commit ids in the summary after a rebase: eighth mention (finding 21).

| # | From | Finding | Class | Resolution |
|---|---|---|---|---|
| 30 | A11 (e2e s22) | After `~/.threads` is copied to another machine, `meta.json` keeps the old folder (`cwd`), so the session-start line does not list the thread for the same project at its new path. Everything else works. | limit (matters for the satellites) | logged for the owner (a way to re-home a thread, or match on the repo instead of the path) |
A11 archived at 14:07Z; A12 = fresh [session id] ("Continue the end-to-end scenario test work", go on without waiting).

**A12 first report (14:07Z).** Found the thread from the session-start line; summary enough and its commit ids matched `git log` (no rebase since the checkpoint); `thread show 11841` for the clipped last message, first try. Finding 20, second hit: it tried `thread show <thread-id>` first; the new error message sent it to `open`/`export` at the cost of one call (two of two fresh sessions since `show` exists tried this: the name invites it).

**B10 milestone (14:13Z).** Guide 12 (the sorites paradox and vagueness) done in new thread `sorites-vagueness-guide`, closed: vault b85dbb9 pushed (the note only), artifact [link removed]. Next: guide 13. Friction, minor (finding 5 again, from a new side): `thread new` captures the session's earlier lines, including what it read from OTHER threads (`thread show -t zeno...`), so the new log holds copies of the old thread's checkpoints and grep matches them; the skill warns about reading other threads while bound, not about the back-capture at `thread new`.

**A12 report 16b (14:15Z).** Scenarios 24 (`show --last` with recovered tails) and 25 (summary file edited, CRLF, Latin-1, removed) committed: 9576375, fc4bcf5. Suite green with five expected failures on both Pythons.

| # | From | Finding | Class | Resolution |
|---|---|---|---|---|
| 31 | A12 (e2e s24) | The `thread show --last K` hint of the recovery line can miss the tail: (a) when the opening session is already bound, its own lines are appended after the hint is computed; (b) when two tails are recovered at once, the first hint shows the second tail. | defect in fix stop 7 | fix stop 8 |
| 32 | A12 (e2e s25) | With `summary.md` removed, `thread open` says "no checkpoint yet" although the log holds a checkpoint. | defect (hand-removed file) | fix stop 8 |
| 33 | A12 (e2e s25) | A non-UTF-8 byte in `summary.md` makes the compaction hook print nothing (strict read). | defect (hand-edited file) | fix stop 8 |

**A12 report 17 (14:23Z).** Scenarios 26 (`meta.json` edited by hand) and 27 (`log.txt`, `.sessions` or a state file removed or damaged) committed: acc5cb1, e262131. Suite green with seven expected failures on both Pythons. Owner question from it: deleting `.sessions` mid-session, or a damaged state file, stops capture silently.

| # | From | Finding | Class | Resolution |
|---|---|---|---|---|
| 34 | A12 (e2e s26) | `save_meta()` writes to the folder named by the `id` inside `meta.json`: closing a thread whose folder was renamed by hand leaves it open and creates a closed ghost folder. | defect (hand rename) | fix stop 8 |
| 35 | A12 (e2e s26) | A non-number `closes` in `meta.json` makes `thread close` crash with a traceback after the checkpoint is already logged. | defect (hand edit) | fix stop 8 |

**Fix stop 8 (findings 31 to 35; 14:28Z to 14:37Z).** A12 interrupted while committing scenario 29, B10 interrupted in guide 13; both archived afterwards. One Fable subagent (in the background this time), reviewed by the coordinator; 51 tests on Python 3.14 and 3.9.
- 31: the recovery line names log lines: `... they are log lines A-B, after later entries: see them with thread show --from A K`; new `thread show --from LINE [N]` (at most 30 entries). Exact when more is appended after the tail and when two tails are recovered.
- 32: with `summary.md` gone, open, export and the compaction text print the last checkpoint entry of the log under a line that says so. 33: `summary.md` is read leniently. 34: meta is written to the folder it was read from. 35: a damaged `closes` counts as 0; no damaged meta field gives a traceback.
- Skill wording: `thread new` also captures what the session read from other threads before.
- Installed in the workshop (local). `companion-skill` rebased before the restart.

**Publication (owner's instruction, 14:24Z).** The owner asked for an updated README and a public repo: push main, Apache-2.0, this log kept but scrubbed (session ids, artifact links, private vault file names), README to say that the tool was mostly developed by AI agents. The one unpushed commit that held session ids was dropped from local history before the push.

**14:37Z restart.** A13 and B11: fresh Opus 5.5 sessions, restart prompts only (plus "do not wait for a go-ahead").

**A13 first report (14:38Z).** Found the thread from the session-start line; the recovery line and two `thread show --from` calls showed scenario 28 committed and scenario 29 written with its commit interrupted; `git status` confirmed. Friction: 44 recovered entries needed two calls (30-entry cap) and 26 of 30 were clipped, so the page said little beyond the assistant lines; it suggests a recovered-tail view limited to assistant and tool_use entries (a `--type` filter on `thread show`). One more open defect from scenario 28 (parallel closes), not yet described.

**B11 first report (14:38Z).** Cold pickup from closed threads: `thread list --all`, `thread grep --all --count`, one grep `--oldest` and one `thread show -t`, all first try. Guide 13: Kuhn. Same note as B9 and B10 on the stale report target in the oldest thread (finding 29).

**14:39Z: published.** threads main pushed (4de4daa) and the repository switched to public (Apache-2.0).

**B11 milestone (14:47Z).** Guide 13 (Kuhn, paradigms and scientific revolutions) done in new thread `kuhn-paradigms-guide`, closed: vault 31e4af3 pushed (the note only), artifact [link removed]. Nothing needed from the log. It noticed the back-capture at `thread new` and found it documented now. Next: guide 14 (Searle's Chinese room). Friction: none in the thread CLI.

**B11 milestone (14:52Z).** Guide 14 (Searle's Chinese room) done in new thread `chinese-room-guide`, closed: vault c689d55 pushed (the note only), artifact [link removed]. Next: guide 15 (Nozick's experience machine). Friction: none.

**B11 milestone (14:56Z).** Guide 15 (Nozick's experience machine) done in new thread `experience-machine-guide`, closed: vault b5fea77 pushed (the note only), artifact [link removed]. Next: guide 16 (Sartre's bad faith). Friction: none.

**A13 report 19 (14:57Z).** The full suite showed the rebase onto the fix-stop-8 commit (7 failures, 4 unexpected successes); `git log -- thread.py` explained it, first try. Tests brought in line (the five defects of fix stop 8 confirmed fixed; one of its own scenario-24 setups was wrong), then scenarios 29 (block types), 30 (detach: no leak through hooks, recovery, re-open or new) and 31 (resume after a close elsewhere). Suite green with three expected failures on both Pythons. Stale repo facts in the summary: ninth mention (finding 21).

| # | From | Finding | Class | Resolution |
|---|---|---|---|---|
| 36 | A12/A13 (e2e s28) | Parallel closes of one thread (details in the scenario-28 expected failure). | defect, rare | fix stop 9 |
| 37 | A13 (e2e s31) | When a session is resumed after its thread was closed by another session, the session-start hook prints nothing, so the resumed agent goes on working uncaptured with no sign (the "closed or removed" message waits for the next thread command). | defect | fix stop 9 |

**B11 milestone (15:00Z).** Guide 16 (Sartre's bad faith) done in new thread `sartre-bad-faith-guide`, closed: vault d8869a2 pushed (the note only), artifact [link removed]. Next: guide 17 (Benacerraf's dilemma). Friction: none.

**B11 milestone (15:04Z).** Guide 17 (Benacerraf's dilemmas) done in new thread `benacerraf-dilemma-guide`, closed: vault dff5c72 pushed (the note only), artifact [link removed]. Next: guide 18 (Zhuangzi's butterfly dream). Friction: none.

**B11 milestone (15:07Z).** Guide 18 (Zhuangzi's butterfly dream) done in new thread `zhuangzi-butterfly-guide`, closed: vault 0e5c5f6 pushed (the note only), artifact [link removed]. Next: guide 19 (Molyneux's problem). Friction: none.

**Fix stop 9 (findings 36, 37; 15:07Z to 15:13Z).** A13 interrupted in its scenario 33 (uncommitted work kept), B11 interrupted in guide 19. One Fable subagent, reviewed by the coordinator; threads main d64f4c8, pushed (the repo is public now); 54 tests on Python 3.14 and 3.9.
- 36: checkpoint and close hold a per-thread lock; of two closes at the same moment exactly one wins, the other gets "thread <id> is closed; only notes can be added".
- 37: the session-start hook says when the session's thread was closed or removed by another session (on resume, compaction and startup); the next thread command still says it once.
- Wish from A13: `thread show --last N` and `--from LINE [N]` take `--type`, so a recovered tail can be read without the long tool results.
- Not covered: a reopen racing a close is still last-writer-wins (in LIMITS.md).
- Installed in the workshop (local). `companion-skill` rebased with autostash before the restart.

**15:13Z restart.** A13 and B11 resumed in place ("Continue.").

**B11 milestone (15:17Z).** Guide 19 (Molyneux's problem) done in new thread `molyneux-problem-guide`, closed: vault bbde6e8 pushed (the note only), artifact [link removed]. Next: guide 20 (Plato's Ring of Gyges). Friction: none.

**A13 report 20 (15:20Z).** After the interrupt it checked `git status` and `git log` rather than the thread, saw the rebase onto the fix-stop-9 commit, and brought scenarios 28 and 31 in line (both defects confirmed fixed). New scenarios 32 (grep patterns an agent writes) and 33 (Windows stdin): 19c63f2, c20aa17. Suite green with three expected failures on both Pythons.

| # | From | Finding | Class | Resolution |
|---|---|---|---|---|
| 38 | A13 (e2e s32) | `thread grep` has no time bound: a pattern with nested repetition (`(a+)+$` against a line of 32 `a`) never returns. | defect (an agent-written regex can hang a turn) | fix stop 10 |
| 39 | A13 (e2e s33) | UTF-16 text on stdin (Windows PowerShell) is stored with NUL bytes; grep finds none of its words and `open` hides it. | defect (Windows) | fix stop 10 |
| 40 | A13 | `thread grep -x` (a pattern that starts with `-`) says "arguments are required: pattern" with no hint to put `--` first; cp1252 stdin silently becomes U+FFFD (the README mentions only `?`). | unclear message, docs gap | fix stop 10 |

**B11 milestone (15:24Z): first compaction in the test.** Guide 20 (Plato's Ring of Gyges) done, thread `ring-of-gyges-guide` closed: vault 6706ec6 pushed (the note only), artifact [link removed]. The session's context was compacted during this guide: the hook re-injected the thread's summary and said 11 entries were newer than the checkpoint, and the session checkpointed again before going on. Next: guide 21 (Wittgenstein's private language argument).
- What compaction cost: the exact payload shape of a docs-tool call that had worked before. The session relearned it from the tool's refusal message and reported that "the thread log held it only in summarised form". Checked by the coordinator: this thread's log holds 11 such calls whole, but all from after the compaction; the calls from before it are in the logs of the earlier guides' threads (one thread per guide). The detail was recoverable with `thread grep --all`, and the session did not think of that. This is finding 29 from another side: a series of threads splits the history, and the post-compaction reminder says "grep" without saying that earlier threads of the same work may hold the detail.

**B11 milestone (15:29Z).** Guide 21 (Wittgenstein's private language argument) done in new thread `private-language-guide`, closed: vault 8cdd23b pushed (the note only), artifact [link removed]. It put the docs payload shape into the new thread's first checkpoint (its own remedy for what compaction cost), and used `thread grep -t <id> --oldest --max 1 --type checkpoint` on five closed threads to correct start times it had guessed for the journal. Friction, minor: `thread list` shows only a date, not a time; a thread's start time takes a grep (or `meta.json`). Next: guide 22.

**A13 report 21 (15:33Z).** Scenarios 34 (header spoof) and 35 (closed pipe) committed: ad2bf87, 6ff9b14. Suite green with six expected failures on both Pythons.

| # | From | Finding | Class | Resolution |
|---|---|---|---|---|
| 41 | A13 (e2e s34) | A tool-result line written in the printed header form (`<id>:<n>  === ... note ===`) looks exactly like a real entry header in `thread show` output (the parser is not fooled, the reader can be). | defect (captured text can imitate the tool's own output) | fix stop 10 |
| 42 | A13 (e2e s35) | `thread open x | head`: when the output is longer than the pipe buffer, the command dies with BrokenPipeError before it binds, so the session stays unbound although the agent saw the summary. grep, show and export print tracebacks on a closed pipe. | defect (agents often pipe to `head`) | fix stop 10, started at once |

**Fix stop 10 (findings 38 to 42; 15:33Z to 15:42Z).** A13 interrupted in its scenario 36, B11 interrupted in guide 22; both archived afterwards. One Fable subagent, reviewed by the coordinator (tests on both Pythons and a smoke run in a temporary home); threads main d3fd733, pushed; 59 tests.
- 42: every command does its state changes first and writes its output at the end; a closed pipe ends it quietly, so `thread open x | head` binds.
- 38: `thread grep` is stopped after 3 s by a small watchdog process (measured: `(a+)+$` stopped at 3.05 s) with a message to simplify the pattern. Cost: one more Python start per grep; a legitimate search over several hundred MB would also be stopped.
- 39: UTF-16 stdin is decoded and NULs are never stored. 40: the grep usage error names `thread grep -- -x`.
- 41: in `thread show` and the open view the header is in column one and every body line is indented two spaces, so captured text cannot imitate a header.
- Wording: the post-compaction text says that earlier threads of the same work hold their own details (`thread grep --all`). `thread list` shows date and time.
- Installed in the workshop (local). `companion-skill` rebased before the restart; its suite is red on purpose again (five expected failures now pass; a few tests and the companion scripts' own tests assert the old `show` and `list` formats).

**15:42Z restart.** A14 and B12: fresh Opus 5.5 sessions, restart prompts only. Cost note: B11 ran for an hour through one compaction and nine guides and cost about 26 USD; the other sessions cost 3 to 9 USD each.

**B12 first report (15:43Z).** Found `is-ought-guide` (guide 22) from the session-start line. `thread open` recovered 19 lines and its `thread show --from 518 19` command worked first try: it showed that the previous session was stopped during the diagram screenshot, with the note written and the artifact up. Friction: the page clipped 15 of 19 entries, so three more `thread show N` calls were needed (the recovery hint could suggest `--type assistant,tool_use`, which now exists).

**B12 milestone (15:45Z).** Guide 22 (Hume's is-ought gap) finished from the interrupted state (three pending artifact sections filled, diagram checked), thread `is-ought-guide` closed; artifact [link removed]. **Vault commit + push refused by the auto-mode classifier** (second time, as for guide 3): the guide-22 note is uncommitted, for the owner. Next: guide 23 (McTaggart on time). Friction: none in the thread tool.

**B12 milestone (15:50Z).** Guide 23 (McTaggart, the unreality of time) done in new thread `mctaggart-time-guide`, closed: vault bc45d2a pushed (the note only), artifact [link removed]. The guide-22 note is still uncommitted. One small gap in a checkpoint (a helper script's argument order) cost one failed call; it added the fact to the closing summary. Next: guide 24. Friction: none in the thread tool.

**B12 milestone (15:54Z).** Guide 24 (the liar paradox) done in new thread `liar-paradox-guide`, closed: vault c8d38cc pushed (the note only), artifact [link removed]. The fact added to the previous closing summary (script argument order) was used first try. Next: guide 25. Friction: none.

**A14 first report (15:56Z).** Found the thread from the session-start line; `thread open` recovered the interrupted session's 6 lines; `thread show 18133`, `thread show --from 18135 6` and one grep, all first try, showed which reports had been sent and that scenarios 36 and 37 were next (the summary itself lagged: it was written before the last two reports). `git log -- thread.py` showed the fix-stop-10 commit; it brought the suite in line (7d71e3f): the five defects of fix stop 10 are confirmed fixed, one expected failure left (finding 30, the owner's). Green on both Pythons.

**B12 milestone (15:57Z).** Guide 25 (Newcomb's problem) done in new thread `newcomb-problem-guide`, closed: vault 1e644a6 pushed (the note only), artifact [link removed]. Next: guide 26. Friction: none.

**B12 milestone (16:01Z).** Guide 26 (the problem of evil) done in new thread `problem-of-evil-guide`, closed: vault 9b7523f pushed (the note only), artifact [link removed]. Next: guide 27. Friction: none.

**A14 report 23 (16:03Z).** Scenarios 36 and 37 committed (ab1e82f, 7936cb7), no new defect: with 300 open threads the session-start line stays one line (8 names and "293 more"), the hook takes 0.05 s, list 0.04 s, `grep --all` 0.14 s; 6 parallel `thread new` with one title get 6 ids. Suite green with one expected failure on both Pythons.

| # | From | Finding | Class | Resolution |
|---|---|---|---|---|
| 43 | A14 (measured, no test) | The 3 s grep bound of fix stop 10 covers the whole search: grep reads about 110 MB/s, so at about 330 MB of logs (`--all`) a plain pattern is stopped with a message that blames the pattern. Also `thread list` has no page bound. | limit of fix 38 with a misleading message (far from today's 5 MB) | next fix stop: the message names both causes and `-t`; or the bound is per line |

**B12 milestone (16:07Z).** Guide 27 (Singer, "Famine, Affluence, and Morality") done in new thread `singer-famine-guide`, closed: vault b75c7cd pushed (the note only), artifact [link removed]. Next: guide 28. Friction: none in the thread tool.

**A14 report 24 (16:09Z).** Scenarios 38 (transcript recreated while bound) and 39 (names with spaces and non-ASCII: work end to end) committed: e197cb8, d2581ad. Suite green with three expected failures on both Pythons.

| # | From | Finding | Class | Resolution |
|---|---|---|---|---|
| 44 | A14 (e2e s39) | The session-start line compares folder paths as strings: the same folder spelled in another letter case or Unicode form (possible on macOS) gets no hint. Matters only if Claude Code passes the typed spelling (not verified). | defect, narrow | fix stop 11 |
| 45 | A14 (e2e s38) | A transcript file that is replaced and grows past the old offset before the next hook loses its first lines silently (a documented limit; the inode or the first line would show the swap). | documented limit with a cheap check | fix stop 11 |

**B12 milestone (16:11Z).** Guide 28 (brains in a vat) done in new thread `brain-in-vat-guide`, closed: vault 011550a pushed (the note only), artifact [link removed]. Friction: none in the thread tool.

**A14 report 25 (16:15Z).** Scenarios 40 (symlinked project folder: no defect) and 41 (subagent transcripts) committed: c637ed7, 34c849c. Suite green with five expected failures on both Pythons.

| # | From | Finding | Class | Resolution |
|---|---|---|---|---|
| 46 | A14 (e2e s41) | A hook that carries an `agent_id` and the subagent's own transcript file passes the "own transcript" check of fix stop 7 (its lines carry the parent's session id), and its length replaces the parent's offset: the next capture repeats or skips lines. Whether Claude Code sends that path is not verified. | defect, if the input occurs | fix stop 11 |

**Fix stop 11 (findings 43 to 46; 16:15Z to 16:21Z).** A14 interrupted after scenario 41, B12 interrupted in guide 29. One Fable subagent, reviewed by the coordinator; threads main 622980d, pushed; 63 tests on Python 3.14 and 3.9.
- 43: the grep stop message tells "stuck on the pattern" from "still reading through very large logs" (by whether lines were still being read) and names the remedy for each.
- 44: the session-start line matches folders by file identity as well as by spelling (letter case and Unicode form no longer matter); still fast with 300 threads.
- 45: the first line of the transcript is fingerprinted with the offset; a replaced file is captured from its start.
- 46: a file in a `subagents` folder never counts as the session's own transcript, and a hook with an `agent_id` cannot set the parent's offset.
- The recovery line suggests `--type assistant,tool_use` when more than 10 entries were recovered.
- Installed in the workshop (local). `companion-skill` rebased before the restart.

**16:21Z restart.** A14 and B12 resumed in place ("Continue.").

**B12 (16:22Z).** After the resume it started guide 29 (Quine, the indeterminacy of translation) in new thread `quine-gavagai-guide`. Friction: none.

**B12 milestone (16:25Z).** Guide 29 (Quine, the indeterminacy of translation) done, thread `quine-gavagai-guide` closed: vault 4e3bd45 pushed (the note only), artifact [link removed]. Friction: none in the thread tool.

**A14 report 26 (16:34Z).** Saw the rebase onto the fix-stop-11 commit by the rule it had put in its own summary ("check `git log -3 -- thread.py`"); findings 44 to 46 confirmed fixed (7d80cc4). Scenario 42 (a 2 MB tool result: stored uncut, clipped in grep/open, whole in `thread show <line>`; a turn-end hook with nothing new reads a 200 MB transcript in 0.10 s): no defect. Scenario 43 (the clock going back): one defect. Suite green with three expected failures on both Pythons.

| # | From | Finding | Class | Resolution |
|---|---|---|---|---|
| 47 | A14 (e2e s43) | A `.lock` file dated in the future (the clock stepped back after a killed holder, or `THREADS_HOME` copied from a machine whose clock is ahead) never counts as stale, so every hook and checkpoint waits until the clock catches up. | defect, rare | next fix stop (age taken as an absolute value) |

**Fix stop 12 (finding 47; 16:54Z to 16:55Z).** Both sessions had ended their turns by themselves after their last reports (A14 at 16:34Z, B12 at 16:25Z), so about 25 minutes of test time were idle on each track: the "do not wait" line of the prompt did not prevent it. One Fable subagent; threads main 72285c7, pushed; 64 tests on both Pythons: a lock whose age is outside the stale window in either direction counts as stale. No skill change. `companion-skill` rebased.

**16:55Z restart.** A15 and B13: fresh Opus 5.5 sessions (restart prompts, plus "do not end your turn after a report"). The last stop is the end of the test at 17:44Z.

**B13 first report (16:56Z).** Cold pickup with 29 closed guide threads: `thread list --all`, `thread grep --all --count`, `thread export` of the newest one, then one grep `--oldest` and `thread show -t <id> 3` for the rules, first try. Next: guide 30 (the Euthyphro dilemma).

| # | From | Finding | Class | Resolution |
|---|---|---|---|---|
| 48 | B13 (seen by B9 to B12 as an extra grep each time) | A closed thread shows only its closing summary, and the skill's closing template has no place for standing rules, so rules written in the first checkpoint are invisible in the summary and the export of a closed thread; each fresh session needs a grep and a `thread show` to get them. | unclear instruction (skill template) | open at the end of the test: add "standing rules (or where they are)" to the closing template |

**A15 first report (17:02Z).** Found the thread from the session-start line; summary enough; `git log -3 -- thread.py` showed the fix-stop-12 commit; finding 47 confirmed fixed (dc96c17). Suite green with one expected failure (finding 30) on both Pythons. Third fresh session of three to try `thread show <thread-id>` first (finding 20): the error message was enough each time, but the guess is natural; an alias (show with an id = the read-only open view) would remove the miss. Stale commit ids after the rebase again (finding 21).

**B13 milestone (17:02Z).** Guide 30 (the Euthyphro dilemma) done in new thread `euthyphro-dilemma-guide`, closed: vault f523e55 pushed (the note only), artifact [link removed]. Its closing summary now repeats the standing rules (its own remedy for finding 48). Next: guide 31. Friction: the back-capture at `thread new` (documented; expected).

**B13 milestone (17:05Z).** Guide 31 (moral luck) done in new thread `moral-luck-guide`, closed: vault 4526e15 pushed (the note only), artifact [link removed]. The rules came straight from the previous closing summary (the remedy for finding 48 worked). It caught a wrong carried fact with `git status`: "guides 1 to 21 committed" had been copied forward through nine or more threads although guide 3 was never committed; `thread export trolley-problem-guide` confirmed it, first try.

| # | From | Finding | Class | Resolution |
|---|---|---|---|---|
| 49 | B13 | A wrong fact in a checkpoint is copied forward from thread to thread in a series; the skill's "verify recorded repo facts" step covers a thread that is opened, not a new thread seeded from its predecessor's summary. | unclear instruction (skill wording) | open at the end of the test |

**B13 milestone (17:09Z).** Guide 32 (Hempel's raven paradox) done in new thread `raven-paradox-guide`, closed: vault 53758cd pushed (the note only), artifact [link removed]. The seed summary was checked against `git status` before use. Next: guide 33. Friction: none new.

**A15 report 28 (17:12Z).** Scenarios 44 (read-only and full disk) and 45 (a bound and an unbound session in one folder: the unbound one writes nothing) committed: 526f650, 0c05e8f. Suite green with two expected failures on both Pythons.

| # | From | Finding | Class | Resolution |
|---|---|---|---|---|
| 50 | A15 (e2e s44) | When the disk fills in the middle of an entry, the cut entry stays in the log, the offset does not advance, and the next capture appends the whole turn again: the turn is in the log twice (the first copy cut). | defect, rare (nothing is lost) | open at the end of the test |
| 51 | A15 (e2e s44) | `thread note` and `thread checkpoint` on a log that cannot be written print a Python traceback, not a one-line `thread:` message. | defect (message) | open at the end of the test |

**B13 milestone (17:13Z).** Guide 33 (Hobbes's state of nature) done in new thread `hobbes-state-of-nature-guide`, closed: vault cf8a128 pushed (the note only), artifact [link removed]. A working mirror for a source that was down was recorded in the closing summary's method. Next: guide 34. Friction: none.

**B13 milestone (17:17Z).** Guide 34 (Kant and the murderer at the door) done in new thread `kant-murderer-door-guide`, closed: vault a3ab3c7 pushed (the note only), artifact [link removed]. Next: guide 35. Friction: none.

**B13 milestone (17:20Z).** Guide 35 (Nagel, "What Is It Like to Be a Bat?") done in new thread `nagel-bat-guide`, closed: vault af3f6a7 pushed (the note only), artifact [link removed]. Next: guide 36. Friction: none.

**A15 report 29 (17:23Z).** Scenarios 46 and 47 committed: 3e9da8c, 8c65c39 (the planned ones were already covered, so it picked new ones). Suite green with four expected failures on both Pythons.

| # | From | Finding | Class | Resolution |
|---|---|---|---|---|
| 52 | A15 (e2e s46) | With a read-only `.sessions` folder the lock cannot be created; the error is taken for the Windows "being deleted" case and retried for ever, so every hook hangs until Claude Code kills it. | defect | fix stop 13 |
| 53 | A15 (e2e s47) | `THREADS_HOME="~/threads"` set unexpanded (an `env` entry in settings.json) puts the thread data in a folder named `~` inside each working folder, that is, inside the project. | defect (breaks "thread data never in a repository") | fix stop 13 |

**Fix stop 13, the last (findings 48 to 53; 17:23Z to 17:31Z).** A15 interrupted after scenario 47, B13 interrupted in guide 36. One Fable subagent, reviewed by the coordinator; threads main be3970b, pushed; 69 tests on Python 3.14 and 3.9.
- 52: every lock wait is bounded (8 s); a lock that cannot be created ends at once: hooks give up quietly, commands say which folder is not writable.
- 53: `THREADS_HOME` is expanded (`~`, variables); a relative value is refused with one line, so thread data cannot land in the project.
- 51: a log that cannot be written gives `thread: cannot write <path>: <reason>`, no traceback. 50: a failed append is rolled back (best effort), so the next capture does not double the turn; the e2e test for it asserts the old cut copy and needs two lines changed.
- 48, 49 (skill): the closing template has a line for standing rules and method; a new thread seeded from an older summary verifies the carried state first.
- Not run on Windows. Installed in the workshop (local). `companion-skill` rebased before the restart.

**17:31Z restart.** A15 and B13 resumed in place ("Continue.") for the last minutes.

**B13 milestone (17:32Z).** Guide 36 (Pascal's wager) finished after the resume in place (only the diagram was pending; nothing reopened or searched): vault 3429d28 pushed (the note only), artifact [link removed], thread `pascal-wager-guide` closed. Friction: none.

**B13 milestone (17:35Z).** Guide 37 (Mill's harm principle) done in new thread `mill-harm-principle-guide`, closed: vault 0342e3f pushed (the note only), artifact [link removed]. A method fact recorded in the previous closing summary worked first try. Friction: none.

**B13 milestone (17:39Z).** Guide 38 (Plato's allegory of the cave) done in new thread `plato-cave-guide`, closed: vault 0fd2010 pushed (the note only), artifact [link removed]. Friction: none.

**B13 milestone (17:42Z).** Guide 39 (Hume, "Of Miracles") done in new thread `hume-miracles-guide`, closed: vault efa5920 pushed (the note only), artifact [link removed]. Friction: none.

## End of the test (17:44Z)

A15 and B13 interrupted and archived at 17:43Z. A15 had confirmed fix stop 13 (89263e9) and committed scenario 48; an uncommitted scenario 49 is left in the worktree. B13 had started guide 40 (thread `aristotle-function-argument-guide`, left open).

| # | From | Finding | Class | Resolution |
|---|---|---|---|---|
| 54 | A15 (e2e s48, not reported before the stop) | A hook killed between the log append and the save of the offset logs the turn twice at the next capture. | defect, rare (nothing is lost) | open |

### Totals

- **Time.** First window 04:55Z to 05:39Z; resumed window 12:17Z to 17:44Z. The coordinator's turn stalled from 05:41Z to 12:11Z (cause not established), so the planned six hours were run in two parts.
- **Sessions.** 28 test sessions in all (tracks A1 to A15 and B1 to B13), Opus 5.5 from B4 and A5 on. Recorded cost of the 19 sessions of the second coordinator: about 131 USD (one session's cost not recorded); the three long track-B sessions were 19 to 26 USD each.
- **Stops.** 13 fix stops; every one stopped both tracks. Sessions were restarted about 35 times: fresh sessions told only "Continue the X work" and sessions resumed in place with "Continue.".
- **Track A.** Three companion skills built, then hardened, brought in line with `thread show`, field notes, a keep-or-fold paper, and an end-to-end suite of 48 scenarios, all on the local branch `companion-skill` (not pushed, nothing installed).
- **Track B.** 39 study guides finished (one thread each from guide 2 on), 37 committed and pushed in the vault by the sessions; two refused by the permission classifier and left for the owner, with the journal file.
- **The tool.** 54 findings; 13 fix stops; unit tests 32 to 69; `thread.py` gained `thread show` (`<line>`, `--last`, `--from`, `--type`), recovery of uncaptured tails at open and close, secret masking at capture, a grep time bound, a per-thread lock, and many clearer messages. Thread data after the test: 50 threads, 11 MB.

### What the stop/restart evidence shows

- **Every restart found its thread**, by the session-start line or `thread list`, and continued without guessing, including cold starts where every thread of the work was closed (the newest closed summary named the next step).
- **Rules given once were kept** by later sessions that were never told them (no push, no install, commit only the guide's own file, do not retry a refused commit), through 39 threads on track B.
- **Searches worked first try** in almost every report. The misses: clipped notes before `thread show` existed (findings 7, 10), and `thread show <thread-id>`, tried first by three of three fresh sessions after `show` existed (finding 20).
- **What an interrupt lost** before fix stop 3: everything after the last capture; once it misled the next session (finding 16). After it, `thread open` recovered the tail every time (4 to 44 transcript lines) and sessions used it to see exactly where the last one stopped.
- **One compaction** happened (B11): the summary came back, the session checkpointed and went on; one detail was lost because it sat in an earlier thread's log (finding 29 and the wording of fix stop 10).
- **Stale facts are the weak point.** Summaries went stale when the repository changed outside the thread (finding 21, ten mentions, all caused by the coordinator's rebases) and when a wrong fact was copied from thread to thread (finding 49). Sessions that checked the disk caught it every time; the tool gives no help.
- **Influenced evidence.** A1, A2, B1, B2, A3 were told about stops. B6 and B8 inferred the purpose of the test from the report questions and paused "for a cold pickup"; later prompts said "do not wait". The coordinator's own actions (rebases under running sessions, one half-finished rebase at 12:58Z) shaped several reports.

### Open at the end

- **Owner decisions:** finding 21 (say at `thread open` when the branch moved under the summary), 29 (link the threads of a series), 30 (a thread keeps its old folder after a move to another machine), 17 (log format for multi-line tool input), 20 (make `thread show <id>` work), file-system compression of closed threads, the masking trade-off (`docs/MASKING-CASES.md` on the companion branch), e2e tests opt-in (the suite takes about 30 s), silent stop of capture when `.sessions` is deleted mid-session.
- **Open defects:** 54 (hook killed between append and offset save: turn logged twice); a reopen racing a close; nothing was run on Windows or Linux.
- **Not done:** the clock times of the first coordinator before 05:28Z were not corrected from the session records; the `companion-skill` branch is unreviewed by the owner and has one uncommitted scenario and one test that asserts the old behaviour of finding 50.
