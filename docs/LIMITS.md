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
- `thread new` in a session that had no thread captures the session from its start. That includes
  what the session read from other threads before (`thread show -t <id> <line>`, `thread grep -t <id> <regex>` or `--all`), so the
  new log can hold copies of older threads' text, and `thread grep` matches those copies. `thread open`
  and `thread reopen` capture from that moment on; what the session did before is not stored.
- When the tool cannot find the session's transcript file at the moment of `thread open` (or of a
  switch to another thread), it captures only lines stamped from that second on. A switch then
  loses the last lines that belonged to the previous thread.
- No hook runs when you interrupt a turn or when a session is killed. That turn is captured by the
  next hook or `thread` command in the same session. If the session is never used again (interrupted,
  then archived), the next `thread open` or `thread close` of that thread from any session captures
  the rest of its transcript, under the earlier session's id, and prints `recovered N transcript lines from session
  <id> that ended without a capture (or is still running); ...`. The recovered entries are appended
  to the log, after entries that are newer by their time stamp; the line names their log lines and ends
  with the command that prints them (`thread show --from A K`), which stays exact when more is
  logged after them. Nothing is recovered when the
  transcript file is gone (deleted, or made on another machine), when that session is bound to
  another thread or detached by then, or for what that session did after the thread was closed
  (`thread reopen` recovers nothing); that work is then not in the log, and nothing says so. A session still running on the same thread is captured early
  by the same step, which is harmless. After `thread close`, the rest of the closing turn is not captured.
- If Claude Code replaces a transcript file with a shorter one, the file is captured again from its
  start (duplicate entries); if it rewrites it at the same or greater length, new lines can be missed.
- Commands and hooks of one session capture one at a time, through a lock file. A lock older than
  5 seconds is taken to be left by a process that died and is removed, so a command waits at most
  that long. `thread checkpoint` and `thread close` of one thread also run one at a time, through
  a lock file of the thread with the same 5 seconds: of two closes at the same moment one wins and
  the other fails with "thread <id> is closed; ...". `thread reopen` and `thread note` do not take it.
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
- `thread grep` and `thread open` clip what they print (400 and 600 characters per line or entry)
  and end the clipped text with `[clipped; thread show N]`, or `[clipped; thread show -t <id> N]`
  when that thread is not (for `open`: will not be) the caller's active thread. `thread show <line>` prints the whole
  entry that contains that log line, however long it is. When `thread open` has more than about
  6000 characters of notes and messages to print, it drops the oldest from the top with no hint.
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
- That includes secrets: the output of `env`, a token in a config file that was read, a key in a
  command line. So do not print secrets while a thread is active. The owner can remove one by
  editing `log.txt` by hand.
- Obvious secrets are masked when text is stored in `log.txt` and `summary.md`: the value becomes
  `[redacted]`, the name and the line stay. This covers obvious patterns only and is not a guarantee:
  - `NAME=value`, `NAME: value`, `"NAME": "value"` (also after `export`), where the name contains
    TOKEN, SECRET, PASSWORD, PASSWD, API_KEY, APIKEY, API-KEY, ACCESS_KEY, PRIVATE_KEY or
    CREDENTIAL, or ends in `_KEY` or `_AUTH`, in any letter case. A bare value ends at the first
    space or quote. Not masked: an empty value, `null`, `true`, `false`, and a number after a
    TOKEN name (`max_tokens: 4096`).
  - `Bearer <16 or more characters>`.
  - Token shapes anywhere: `sk-…` (20 or more characters), `ghp_…` and the other `gh?_` prefixes,
    `github_pat_…`, `xox[baprs]-…`, `AKIA` plus 16 characters.
  - The body lines of a PEM private key block, and of a PGP one (`-----BEGIN PGP PRIVATE KEY
    BLOCK-----`), at most 200 lines; the BEGIN and END lines stay.
  It cannot be turned off and has these effects:
  - A secret in any other form is stored as it is: a password as a command argument
    (`--password x`, `-p x`), one inside a URL, a name without those words, a value on the line
    after its name.
  - A quoted value with an escaped quote is masked only up to it: `TOKEN='a\'b'` is stored as
    `TOKEN='[redacted]'b'`, so the tail stays.
  - Ordinary text of the same form is masked too: `token = get_token()` or `password: str` in
    source code is stored as `token = [redacted]`, `password: [redacted]`.
  - `thread grep` for a masked value finds nothing; search for the name.
  - The session transcript under `~/.claude/projects` is not masked, and neither is the thread
    title, log text stored before this version, or anything on the screen.
  - If the masking step itself fails, the text is stored unmasked: a write is never lost to it.
- A summary records facts about a repository (branch head, commit ids) as they were at the
  checkpoint. The repository can change outside the thread, so verify them (`git log`) on resume.
- The session-start line lists an open thread when the session's folder and the folder the thread
  was created in are the same or one is inside the other, at most 8, most recent log activity
  first. A session started in a root folder, and a thread created in one, get no line. A session
  started in a high folder (the home folder) is told about every thread below it.
- Files edited by hand: when `summary.md` is gone, `thread open`, `thread export` and the text after a
  compaction print the last checkpoint entry of the log instead, under a line that says so; bytes in it
  that are not UTF-8 are shown as `�`. The folder name is the thread id: a folder renamed by hand keeps
  working, and the next `close` or `reopen` corrects the `id` in its `meta.json`. A `closes` that is
  not a number counts as 0, and `thread close` says so.
- `thread list` shows the date and time (to the minute) of the last log activity in UTC, as the
  log and `meta.json` do; they can differ from the local date and time.
- `thread grep` stops a search after 3 s, with a message that says to simplify the pattern: a
  pattern with a repeat inside a repeat can otherwise run without end. A second small Python
  process watches the time (the regex engine cannot be interrupted from inside the process on
  Windows), so each `thread grep` starts one. On a machine where it cannot be started, the search
  has no time bound. A search of several hundred MB of logs can reach the 3 s too: narrow it with `-t`.
- Text on stdin (`note`, `checkpoint`, `close`) is read as UTF-8 or, by its byte-order mark or NUL
  bytes, as UTF-16; NUL characters are never stored. Bytes of another encoding (cp1252) that are not
  valid UTF-8 become `�` (U+FFFD). UTF-16 without a mark is taken as little-endian or big-endian by
  where most of its NUL bytes are, which is right for text that is mostly Latin letters.
- Output is written when a command is done. A reader that closes the pipe early (`| head`) does not
  stop the command's work and gets no error; the exit status is then 0.
- In `thread show`, only a line in the first column is an entry header; body lines are indented by
  two spaces (empty lines stay empty). `thread open` indents the later lines of each entry the same
  way, and `thread grep` prints body lines under their line number. The summary is printed as written.
- Inside an entry, unusual line separators (form feed, U+2028, CR) are stored as newlines, and a
  body line that starts with `=== ` gains a leading space.
- A resumed session keeps its id and its binding. A forked session (`--fork-session`, `/branch`)
  gets a new id and starts with no active thread. Its transcript begins with a copy of the parent's
  history; the session-start hook marks the fork point so that `thread new` there captures only what
  the fork itself did. Without the hooks installed, `thread new` in a fork captures the copied
  history too.
- Lines in a transcript that carry another session's id are not captured.
  A hook's `transcript_path` is used only when the file is named `<session id>.jsonl` or holds a line
  of that session; otherwise the session's own file is looked up as when no path is given.
- When one session closes or removes a thread, another session bound to it is detached at its next
  capture. Its next `thread` command that uses the active thread fails once with `thread <id> was
  closed or removed by another session, ...`, also when a hook ran in between; after that the
  session has no active thread. Until then, each session start of it (resume and compaction too)
  prints `Thread <id> was closed or removed by another session, ...`. `thread close` first captures what that session did up to the close
  if its transcript file is on disk; what it did after the close, or before a removal and after its
  last capture, is not stored. This holds even if the thread is reopened or recreated in between;
  run `thread open` to bind again.
- A session that gets a new session id (for example after `/clear`) is not bound; run `thread open`
  again.
- Search is lexical. If you cannot guess a word that was used, you will not find the entry.

## Not in v1

Each of these was considered and left out. Add one when its trigger shows up.

| Left out | Why | Add it when |
|---|---|---|
| Full secret redaction (entropy scan, rewriting old log text, masking the transcript) | Scanning is unreliable; only obvious patterns are masked (see Limits). | Logs must leave the machine, or policy requires it. |
| Truncation of long tool outputs | The point of the pattern is a log that keeps what the transcript holds. | Disk use becomes a problem. |
| Compressing or archiving closed threads | Plain files are simpler to search and inspect. | `~/.threads` grows past a few GB. |
| Plugin packaging | Work may block plugin marketplaces; a few manual steps are enough. | Several people install it. |
| An install command | Code that edits `settings.json` is a risk for little gain. | The manual steps cause errors. |
| More statuses (paused, blocked) | Open and closed cover the lifecycle; the summary says the rest. | `thread list` cannot answer "what is waiting". |
| Per-kind templates | Kind is only a label. | Bug and project summaries clearly need different headings. |
| Parent/child links | Threads are flat; name the related id in a note. | Related threads become hard to find with `grep --all`. |
| Capture of subagents' internal steps | Logs would grow many times over. | A subagent's internal steps are needed for recall. |
| Locking between sessions | Each session has its own lock for capture; a thread has one for checkpoint and close only. Appends from different sessions are one write each (atomic on POSIX, and on Windows through `FILE_APPEND_DATA`); the summary is the last checkpoint written, with every version in the log. | Two sessions on one thread lose or interleave entries. |
| `thread delete` | `rm -rf ~/.threads/<id>` does it. | A retention rule needs an audited command. |
| `thread rename` | Ids are rarely typed in full; a prefix works. | A title turns out badly wrong often. |
