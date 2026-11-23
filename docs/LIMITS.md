# Limits and what is not in v1

What the tool does not capture or guarantee, and the features that were considered and left out.
The short version is in the [README](../README.md#what-it-does-not-capture).

## Limits

- Capture reads Claude Code's transcript files, whose format is not documented and may change.
- Only the main session is captured. A subagent's work appears as the prompt it was given and the
  report it handed back; its internal steps are not captured.
- Capture runs when a turn ends (also when it ends in an API error), before compaction, at session
  start and end, and on `new`, `open` (of an open thread), `reopen`, `note`, `checkpoint`, `close`, `detach`
  and the first page of `grep`.
- `thread new` in a session that had no thread captures the session from its start. `thread open`
  and `thread reopen` capture from that moment on; what the session did before is not stored.
- When the tool cannot find the session's transcript file at the moment of `thread open` (or of a
  switch to another thread), it captures only lines stamped from that second on. A switch then
  loses the last lines that belonged to the previous thread.
- No hook runs when you interrupt a turn or when a session is killed. That turn is captured by the
  next hook or `thread` command in the same session, or not at all if the session is never used
  again. After `thread close`, the rest of the closing turn is not captured.
- If Claude Code replaces a transcript file with a shorter one, the file is captured again from its
  start (duplicate entries); if it rewrites it at the same or greater length, new lines can be missed.
- Commands and hooks of one session capture one at a time, through a lock file. A lock older than
  5 seconds is taken to be left by a process that died and is removed, so a command waits at most
  that long.
- A background subagent's finishing notice and a message from another agent are logged with the
  entry type `subagent`. A subagent's report is captured in whichever form Claude Code delivers it:
  as the `tool_result` of its Agent call, or as a separate message turn (entry type `subagent`;
  recognised by how the message starts: `<agent-message`, `<cross-session-message` or `Another
  Claude session sent a message`). A report in a form that starts differently is logged as a
  `user` entry, or left out if Claude Code marks it as injected. A background shell's notice is
  `notification`; Claude Code's own summary at a compaction is
  `compaction`. Slash commands you type and their local output are `user` entries.
- A message that arrives while a turn is running (your own words, a notice, a report) can appear in
  the transcript twice, once queued and once as a user line. Both are logged: the tool never drops
  an entry because its text was seen before.
- When Claude Code writes the same transcript line twice, one copy is kept, but only within one
  capture run.
- Thinking is stored only when the transcript holds its text. Current Claude Code leaves most
  thinking blocks empty.
- `thread grep` and `thread open` clip what they print (400 and 600 characters per line or entry).
  For the full text, read `~/.threads/<id>/log.txt` at the `thread:line` that grep shows.
- Recall costs tokens and does not always help: in the paper, on a task where summaries were
  enough, grep used 2.3 times the tokens for no significant gain.
- `thread grep` has no time limit; a pattern with several `.*` on a very long line can run for a
  long time.
- Matches are listed newest first (the paper lists oldest first). If new matching entries are
  captured between two pages, some matches can appear twice; none is skipped.
- Claude Code writes the transcript asynchronously, so a capture can miss the newest lines. The next
  capture takes them.
- A transcript line the tool cannot read is skipped and recorded as an `event` entry.
- Claude Code itself stores a very large tool output in the transcript as a short preview plus a
  file path. The log gets what the transcript holds, so it has only the preview, and Claude Code
  deletes the file it points to after 30 days by default.
- `thread grep` calls and their output are stored but never searched, because the output only
  repeats the log. This applies to any Bash or PowerShell command that runs `thread grep`, alone or
  chained (`cd x && thread grep y`), so other output of that command cannot be found by a search
  either. A command that only mentions the words inside quotes or a heredoc (a commit message, a
  file being written) is not affected. The rule recognises the usual ways of running a command
  (after `;`, `&&`, `|`, in a loop, behind `env`, `rtk`, `time`, `xargs`, a Python launcher); an
  unusual wrapper is not recognised, and that call's output is then searched like any other.
- Everything a command prints in a bound session is captured into its active thread, including
  text of other threads: the output of `thread grep --all` or `thread export <other>`, files read
  under `~/.threads`, a script that summarises all threads. `thread grep` skips its own earlier
  output at search time; the output of every other command is searched like anything else, so
  another thread's text can come back as a match in this one.
- The session-start line lists an open thread when the session's folder and the folder the thread
  was created in are the same or one is inside the other, at most 8, most recent log activity
  first. A session started in a root folder, and a thread created in one, get no line. A session
  started in a high folder (the home folder) is told about every thread below it.
- `thread list` shows the day of the last log activity in UTC, as the log and `meta.json` do; it
  can differ from the local date.
- Inside an entry, unusual line separators (form feed, U+2028, CR) are stored as newlines, and a
  body line that starts with `=== ` gains a leading space.
- A resumed session keeps its id and its binding. A forked session (`--fork-session`, `/branch`)
  gets a new id and starts with no active thread. Its transcript begins with a copy of the parent's
  history; the session-start hook marks the fork point so that `thread new` there captures only what
  the fork itself did. Without the hooks installed, `thread new` in a fork captures the copied
  history too.
- Lines in a transcript that carry another session's id are not captured.
- When one session closes or removes a thread, another session bound to it is detached at its next
  capture (its next `thread` command says so), and what that session did since its last capture is not stored. This holds even if the
  thread is reopened or recreated in between; run `thread open` to bind again.
- A session that gets a new session id (for example after `/clear`) is not bound; run `thread open`
  again.
- Search is lexical. If you cannot guess a word that was used, you will not find the entry.

## Not in v1

Each of these was considered and left out. Add one when its trigger shows up.

| Left out | Why | Add it when |
|---|---|---|
| Secret redaction | Scanning is unreliable and the same text is already in Claude Code's transcripts. | Logs must leave the machine, or policy requires it. |
| Truncation of long tool outputs | The point of the pattern is a log that keeps what the transcript holds. | Disk use becomes a problem. |
| Compressing or archiving closed threads | Plain files are simpler to search and inspect. | `~/.threads` grows past a few GB. |
| Plugin packaging | Work may block plugin marketplaces; a few manual steps are enough. | Several people install it. |
| An install command | Code that edits `settings.json` is a risk for little gain. | The manual steps cause errors. |
| More statuses (paused, blocked) | Open and closed cover the lifecycle; the summary says the rest. | `thread list` cannot answer "what is waiting". |
| Per-kind templates | Kind is only a label. | Bug and project summaries clearly need different headings. |
| Parent/child links | Threads are flat; name the related id in a note. | Related threads become hard to find with `grep --all`. |
| Capture of subagents' internal steps | Logs would grow many times over. | A subagent's internal steps are needed for recall. |
| Locking between sessions | Each session has its own lock for capture. Appends from different sessions are one write each (atomic on POSIX, and on Windows through `FILE_APPEND_DATA`); the summary is last-writer-wins with every version in the log. | Two sessions on one thread lose or interleave entries. |
| `thread delete` | `rm -rf ~/.threads/<id>` does it. | A retention rule needs an audited command. |
| `thread rename` | Ids are rarely typed in full; a prefix works. | A title turns out badly wrong often. |
