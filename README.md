# threads

A CLI and Claude Code skill that give a coding agent **threads**: long-lived units of work (a project,
a feature, an idea, a bug) that survive across sessions.

The design follows GrepMem, ["Forget Freely, Grep Later"](https://arxiv.org/abs/2611.25123): keep an
append-only plain-text log of the session, keep one summary in context, and recall details with
case-insensitive regex search. No index, no embeddings, no database. The grep limits (10 matches per
page, at most 30; 1 context line, at most 3; about 6,000 characters per page) are the paper's. Two
things differ: the paper's agent writes its summary at every compaction and may grep only after the
first one, while here the summary is a checkpoint the agent writes by hand and grep is always
available. The paper tested one RL-trained model on single-episode benchmarks, not coding agents or
work across sessions.

- One Python 3 file, standard library only, no network access.
- All data in `~/.threads/` (directories mode 0700, files 0600), never in a repository.
- Terms are defined in [GLOSSARY.md](GLOSSARY.md); decisions in [docs/adr/](docs/adr/).

## How it works

- `thread new` or `thread open` binds the current Claude Code session to a thread.
- Hooks append the session transcript to that thread's `log.txt`: user and assistant messages,
  thinking, tool calls and tool results, as the transcript holds them and with nothing cut by this
  tool. Images are logged as `[image]`. Lines that Claude Code injects (system lines, attachments,
  skill instructions, reminders, its own compaction summary) are not captured. See
  [Limits](#limits) for the exceptions.
- The agent writes notes and, at milestones, a checkpoint that replaces `summary.md`.
- A later session runs `thread open`, reads the summary, and uses `thread grep` for the details.
- After Claude Code compacts the context, a hook re-injects the summary, says how many entries are
  newer than it, and reminds the agent to grep.

## Install

Needs Python 3.9+ and Claude Code 2.1.132 or later (older versions do not tell the tool which
session it is in, so nothing is captured). Nothing is downloaded.

### macOS and Linux

1. Put `thread.py` on your `PATH` as `thread`:

   ```sh
   mkdir -p ~/.local/bin
   ln -s "$PWD/thread.py" ~/.local/bin/thread
   ```

   `~/.local/bin` must be on your `PATH`; `thread --help` must work in a new terminal.

2. Copy the skill:

   ```sh
   mkdir -p ~/.claude/skills && cp -r skill/thread ~/.claude/skills/
   ```

   The result must be `~/.claude/skills/thread/SKILL.md`.

3. Merge the `hooks` block of [hooks.json](hooks.json) into `~/.claude/settings.json`. If you already
   have hooks for an event, append the whole `{ ... }` group from `hooks.json` to that event's list.
   For `SessionStart` it must stay a group of its own with `"matcher": "compact"`. On Claude Code
   older than 2.1.78 the `StopFailure` entry is skipped with a warning; that is harmless.

4. Optional: allow the command, so each call does not ask for permission. Add `"Bash(thread:*)"` to
   `permissions.allow` in `~/.claude/settings.json`.

Without step 3, capture happens only when a `thread` command runs, and nothing is re-injected after
compaction.

`thread` must be on the `PATH` that Claude Code itself was started with, because hooks inherit it.
Settings changes are normally picked up by a running session; if the hooks do not fire, start a new
one. `/hooks` must list the five entries. Hooks do not run until you have accepted the trust dialog
for the folder, and never in `claude --bare` runs.

### Windows

Tested on Windows 11 with Python 3.10, Windows PowerShell 5.1 and Git Bash, outside Claude Code.
Not tested: real Claude Code sessions on Windows, and PowerShell 7.

1. Copy `thread.py` to a folder of its own, for example `%USERPROFILE%\bin`, and put that folder on
   your `PATH`. Python is `python` or `py` there, not `python3`.

2. In the same folder, create **two** wrappers. Claude Code runs hooks in Git Bash when Git for
   Windows is installed and in PowerShell otherwise, and the agent's own commands can use either.

   `thread.cmd` (for cmd and PowerShell):

   ```bat
   @python "%~dp0thread.py" %* || exit /b 1
   ```

   `thread` with no extension (for Git Bash, which does not find `thread.cmd`):

   ```sh
   #!/bin/sh
   MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*' python "$(dirname "$0")/thread.py" "$@" || exit 1
   ```

   The `|| exit` parts matter. If Python cannot be started or the path is wrong, the exit code is
   2, and Claude Code reads exit code 2 from a hook as "block the compaction" (and, in some cases,
   the turn). The `MSYS` variables stop Git Bash from rewriting text that starts with `/`.

3. Copy the `skill\thread` folder to `%USERPROFILE%\.claude\skills\thread\`.

4. Merge [hooks.json](hooks.json) into `%USERPROFILE%\.claude\settings.json` as in step 3 above.

5. Optional: add both `"Bash(thread:*)"` and `"PowerShell(thread *)"` to `permissions.allow`.

Things to know on Windows:

- **In PowerShell, pass text on stdin, never as arguments.** PowerShell hands `thread.cmd` an
  unquoted argument when it contains no space, so cmd treats `|`, `<` and `>` in it as operators and
  **runs whatever follows `&` as a command**. Pipe a here-string: a line `@'`, the text, then a
  line `'@ | thread note`. For a regex with `|`, `&`, `<` or `>`, call Python directly:
  `python "$env:USERPROFILE\bin\thread.py" grep 'timeout|timed out'`.
- Windows PowerShell 5.1 drops double quotes inside an argument, and in your own terminal it turns
  non-ASCII characters in piped text into `?` (set `$OutputEncoding` to UTF-8 to avoid it). Inside
  Claude Code, piped text is sent as UTF-8.
- File modes do nothing on Windows; the data folder has the permissions of your user profile.
- A managed policy can stop user hooks (`allowManagedHooksOnly`), personal skills
  (`strictPluginOnlyCustomization`) or your allow rules (`allowManagedPermissionRulesOnly`).
  `/hooks` and `/status` show what is in force. The tool still works without hooks (see above).
- The SessionEnd hook has a 10-second limit in `hooks.json`. A hook took about 0.1 s on the test
  machine; raise the limit if antivirus scanning makes Python slow to start.

### Check the install

The check must be made from outside the session, because a `thread` command run by the agent
captures by itself and would hide a missing hook.

1. In a new Claude Code session, ask for `thread new install check`.
2. In a separate terminal, run `thread grep --count . -t install-check` and note the number.
3. In the session, send one ordinary message (for example "say hello") and wait for the reply. Do
   not ask for any `thread` command.
4. Run the command from step 2 again. The number must be higher. If it is not, the Stop hook did
   not run: check that `thread` is on the `PATH` Claude Code was started with and that hooks are
   allowed (`/hooks`).
5. `~/.threads/errors.log` must not exist. If it does, it holds the hook's traceback.
6. The hook must exit with 0 when run by hand. Git Bash, macOS, Linux:
   `echo '{}' | thread hook; echo $?`. PowerShell: `'{}' | thread hook; $LASTEXITCODE`.
7. Remove the test thread: `rm -rf ~/.threads/install-check`, or in PowerShell
   `Remove-Item -Recurse -Force "$env:USERPROFILE\.threads\install-check"`.

## Daily use

- **Every new session, and every `/clear`, starts with no active thread, and nothing says so.**
  Until you say "open the X thread" (or start a new one), that session is not captured. To check,
  ask the agent for `thread list`: `*` marks the active thread. A `thread list` in your own
  terminal never shows `*`, because the terminal is not a Claude Code session.
- `thread list` shows open threads; `thread list --all` includes closed ones. To find a thread by
  what was said in it: `thread grep --all --count '<word>'`.
- A subagent runs `thread` commands with the main session's id. If it runs `thread new` or
  `thread open`, it moves the main session's capture to that thread.
- `thread note` from your own terminal needs `-t <id>`.
- **Upgrade:** replace `thread.py` and the skill folder with the new copies. Merge `hooks.json`
  again only when the release notes in `docs/LOG.md` say it changed.
- **Move to another machine:** copy `~/.threads` without its `.sessions` folder.
- **Clean up:** `.sessions` gains one small file per session that was ever bound; delete the folder
  when no Claude Code session is running. `log.txt` is plain text and nothing indexes it, so you
  can edit it by hand, for example to remove a secret that was printed.

## Troubleshooting

| Sign | Likely cause |
|---|---|
| `thread list` (run by the agent) shows no `*` | New session or `/clear`; or another session closed or removed the thread. Say "open the X thread". |
| `no Claude Code session id: nothing bound` | Claude Code older than 2.1.132, or the command was run outside Claude Code. |
| The count in "Check the install" does not rise | `thread` not on the `PATH` Claude Code was started with; hooks blocked by policy (`/hooks`); folder not trusted. |
| `thread list` prints "hook errors are recorded in ..." | Read `errors.log`; it holds the traceback. Delete it when solved. |
| The same lines appear twice in a log | A forked session was opened on its parent's thread, a state file was lost, or two captures ran at once (see Limits). |

## Commands

| Command | Does |
|---|---|
| `thread new <title> [--kind K]` | Create a thread and bind this session. A session with no earlier thread is captured from its start. The title becomes the id (lower case, at most 50 characters), so keep it to a few words. The kind is a free label and is case-sensitive. |
| `thread list [--all] [--kind K]` | List open threads, newest activity first. `*` marks the active one. |
| `thread open <id>` | Print the summary and what came after the last checkpoint; bind this session. A closed thread is shown read-only. A unique id prefix is enough. |
| `thread note <text>` | Append a note (text as arguments or on stdin). Prints how many entries are newer than the last checkpoint. |
| `thread checkpoint` | Replace the summary (text as arguments or on stdin). Warns above 6000 characters, the amount re-injected after a compaction. |
| `thread grep <regex>` | Case-insensitive search of the log. `--count`, `--max N` (10, max 30), `--offset N`, `--context N` (1, max 3), `--all` for every thread. A page ends early at about 6000 characters; the footer gives the `--offset` of the first match not shown. Context lines stay inside the matching entry. Printed lines are clipped to 400 characters. Earlier `thread grep` calls are not searched. Options go before a `--`. |
| `thread detach` | Stop capturing this session. |
| `thread close` | Close with a final summary (arguments or stdin). The log is kept. |
| `thread reopen <id>` | Reopen a closed thread and bind this session. Fails on an open thread. |
| `thread export <id>` | Print the summary and all notes as markdown. |
| `thread hook` | Hook entry point; reads Claude Code's hook JSON on stdin. |

`note`, `checkpoint`, `close` and `grep` use the session's active thread; `-t <id>` names another.
Put `-t` before the text: everything after the first word of text is taken as text. Text whose
first word starts with `-` needs `--` before it (`thread note -- --max was wrong`). Use stdin for
text with quotes, backticks or `$`. `checkpoint` and `close` refuse a closed thread; `note -t`
still adds to one.

## Data

```
~/.threads/
  <id>/meta.json     id, title, kind, status, created, cwd, uid, closes
  <id>/log.txt       append-only; each entry starts "=== <time> <session id, 8 chars> <entry type> [tool] ==="
  <id>/summary.md    current summary
  .sessions/         which thread each session is bound to, and how much of it is captured
  errors.log         hook failures (a hook never blocks a session)
```

`THREADS_HOME` overrides the directory. To remove a thread: `rm -rf ~/.threads/<id>`. A session
bound to a removed or closed thread is treated as detached.

The log contains whatever your tools printed, including any secrets, and text from other
programs and web pages. Treat it as a record, not as instructions.

**Retention.** Claude Code deletes its own transcripts after 30 days by default. `~/.threads` keeps
its copy until you remove it; nothing is deleted automatically. If a retention rule applies to your
work, remove old threads yourself (`rm -rf ~/.threads/<id>`). `thread grep --all` reads every
thread, so text from one piece of work can reach a session working on another.

## Limits

- Capture reads Claude Code's transcript files, whose format is not documented and may change.
- Only the main session is captured. A subagent's work appears as the prompt it was given and the
  report it returned.
- Capture runs when a turn ends, before compaction, at session end, and on `new`, `open` (of an
  open thread), `reopen`, `note`, `checkpoint`, `close`, `detach` and the first page of `grep`.
- No hook runs when you interrupt a turn or when a session is killed. That turn is captured by the
  next hook or `thread` command in the same session, or not at all if the session is never used
  again. After `thread close`, the rest of the closing turn is not captured.
- If Claude Code replaces a transcript file with a shorter one, the file is captured again from its
  start (duplicate entries); if it rewrites it at the same or greater length, new lines can be missed.
- Two captures of one session at the same moment (for example parallel subagents each running a
  `thread` command) can store the same lines more than once.
- Subagent results come back to the session as `user` lines, so they are logged as `user` entries.
- Thinking is stored only when the transcript holds its text. Current Claude Code leaves most
  thinking blocks empty.
- `thread grep` and `thread open` clip what they print (400 and 600 characters per line or entry).
  For the full text, read `~/.threads/<id>/log.txt` at the `thread:line` that grep shows.
- Recall costs tokens and does not always help: in the paper, on a task where summaries were
  enough, grep used 2.3 times the tokens for no significant gain.
- `thread grep` has no time limit; a pattern with several `.*` on a very long line can run for a
  long time.
- Tool calls are stored as one JSON line, so quotes and backslashes in a command appear escaped
  (`\"`, `\\`). Search for words of the command, not for the command as typed.
- With `--all`, pages are numbered across threads in id order. If another session adds matching
  entries between two pages, some matches can appear twice; none is skipped.
- Claude Code writes the transcript asynchronously, so a capture can miss the newest lines. The next
  capture takes them.
- A transcript line the tool cannot read is skipped and recorded as an `event` entry.
- Claude Code itself stores a very large tool output in the transcript as a short preview plus a
  file path. The log gets what the transcript holds, so it has only the preview, and Claude Code
  deletes the file it points to after 30 days by default.
- The output of `thread grep` is not stored: the call is logged and its result is replaced by a
  marker, because it only repeats the log. This applies to any shell command that runs
  `thread grep`, alone or chained (`cd x && thread grep y`), so other output of that command is
  lost with it. A command that only mentions the words (a commit message) is not affected.
- Inside an entry, unusual line separators (form feed, U+2028, CR) are stored as newlines, and a
  body line that starts with `=== ` gains a leading space.
- A resumed session keeps its id and its binding. A forked session (`--fork-session`, `/branch`)
  gets a new id and starts with no active thread; its transcript begins with a copy of the parent's
  history, so `thread new` or `thread open` in a fork captures that history a second time.
- Lines in a transcript that carry another session's id are not captured.
- When one session closes or removes a thread, another session bound to it is detached at its next
  capture, and what that session did since its last capture is not stored. This holds even if the
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
| Plugin packaging | Work may block plugin marketplaces; three manual steps are enough. | Several people install it. |
| An install command | Code that edits `settings.json` is a risk for little gain. | The manual steps cause errors. |
| More statuses (paused, blocked) | Open and closed cover the lifecycle; the summary says the rest. | `thread list` cannot answer "what is waiting". |
| Per-kind templates | Kind is only a label. | Bug and project summaries clearly need different headings. |
| Parent/child links | Threads are flat; name the related id in a note. | Related threads become hard to find with `grep --all`. |
| Subagent capture | Logs would grow many times over. | A subagent's internal steps are needed for recall. |
| Locking | Appends are one write per entry (atomic on POSIX); the summary is last-writer-wins with every version in the log. Two captures of the same session at the same instant can duplicate entries. | Duplicate or lost entries appear. |
| `thread delete` | `rm -rf ~/.threads/<id>` does it. | A retention rule needs an audited command. |
| `thread rename` | Ids are rarely typed in full; a prefix works. | A title turns out badly wrong often. |

## Development

```sh
python3 -m unittest discover -s tests
```
