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
