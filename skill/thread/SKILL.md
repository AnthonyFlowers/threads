---
name: thread
description: Create, resume, search and close "threads" - long-lived units of work (project, feature, idea, bug) with a complete searchable log and a summary, via the local `thread` CLI. Use for /thread new|open|close|list|note|grep|checkpoint|detach|export, or "start a thread for...", "pick up / continue the X thread", "what threads are open", "close out this thread", "what did we decide about X" while a thread is active.
---

# thread

A thread is one unit of work that outlives a session. It has an append-only **log** (hooks capture the
whole session transcript into it; nothing is dropped), a **summary** (the current state) and a **kind**
label. You forget freely; the log does not. Search it instead of re-deriving.

All commands are the local `thread` CLI. It uses no network.

## Rules

- Create, open, close or reopen a thread **only when the user asks**. Never start one on your own.
- While a thread is active, do these without being asked:
  - **Checkpoint** when a piece of work completes and before you stop for the day.
  - **Grep the log** before re-deriving a fact, re-reading files you already analysed, or retrying
    something that may already have failed. After a context compaction, assume details are missing
    from your context and grep for them.
  - **Note** decisions with their reason, dead ends, and anything the user tells you that a later
    session must know. Capture is automatic, but notes are what resume and export show first.
- If the user turns to unrelated or sensitive work in the same session, offer `thread detach`.

## Commands

| Do this | Command |
|---|---|
| Start a thread | `thread new <title> --kind <project\|feature\|idea\|bug\|...>` |
| See open threads | `thread list` (`--all` includes closed, `--kind bug` filters) |
| Resume a thread | `thread open <id-or-unique-prefix>` |
| Record a decision or finding | `thread note <text>` |
| Replace the summary | `thread checkpoint` with the summary on stdin |
| Recall details | `thread grep <regex>` |
| Stop capturing this session | `thread detach` |
| Close out | `thread close` with the final summary on stdin |
| Reopen a closed thread | `thread reopen <id>` |
| Hand the result to someone | `thread export <id>` (summary + notes as markdown, to stdout) |

`note`, `checkpoint`, `close` and `grep` act on the active thread; pass `-t <id>` for another one.

### Starting

`thread new` binds this session. If the session had no thread before, everything said so far in the
session is captured too. Follow it with a first checkpoint stating the goal.

### Resuming

`thread open` prints the summary, then, if the last session ended without a checkpoint, the count of
newer entries with the notes and latest messages. Read it, grep for what you still need, and
checkpoint once you have caught up. A closed thread is shown read-only and is not bound.

### Checkpoint template

Pass it on stdin (a heredoc). Keep it short enough to read in one go; details belong in the log.

```
thread checkpoint <<'EOF'
## Goal
## State
## Decisions (with why)
## Dead ends
## Next steps
## Open questions
EOF
```

### Searching

`thread grep` is a case-insensitive regex over the log lines. Matching is lexical, so guess the words
that were actually used and try alternatives (`timeout|timed out|ETIMEDOUT`).

- `--count` first when a pattern may be broad.
- 10 matches per page; follow the `--offset N` hint for the next page; `--max` up to 30.
- `--context 0..3` lines around each match (default 1).
- `--all` searches every thread, open and closed. Use it to find earlier work on the same subject.
- Each match shows `thread:line` and the entry header (time, session, and `user`, `assistant`,
  `tool_use <name>`, `tool_result`, `note`, `checkpoint`). Grep `tool_use Bash` or `=== .* note` to
  search by entry type.

### Closing

`thread close` needs the final summary on stdin, using the checkpoint template. Make the **first line
the outcome**: `Outcome: done`, `Outcome: abandoned - <why>`, or `Outcome: superseded by <id>`.
The log is kept and stays searchable. Closing also detaches the session.
