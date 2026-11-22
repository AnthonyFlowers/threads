# threads

A CLI and Claude Code skill that give a coding agent **threads**: long-lived units of work (a project,
a feature, an idea, a bug) that survive across sessions.

The design follows GrepMem, ["Forget Freely, Grep Later"](https://arxiv.org/abs/2611.25123): keep an
append-only plain-text log of everything, keep one summary, and recall details with regex search. No
index, no embeddings, no database.

- One Python 3 file, standard library only, no network access.
- All data in `~/.threads/` (directories mode 0700, files 0600), never in a repository.
- Terms are defined in [GLOSSARY.md](GLOSSARY.md); decisions in [docs/adr/](docs/adr/).

## How it works

- `thread new` or `thread open` binds the current Claude Code session to a thread.
- Hooks append the session transcript to that thread's `log.txt`: user and assistant messages,
  thinking, tool calls and tool results, as the transcript holds them and with nothing cut by this
  tool. Images are logged as `[image]`. Lines that Claude Code injects (system lines, attachments,
  skill instructions, reminders) are not captured. See [Limits](#limits) for the exceptions.
- The agent writes notes and, at milestones, a checkpoint that replaces `summary.md`.
- A later session runs `thread open`, reads the summary, and uses `thread grep` for the details.
- After Claude Code compacts the context, a hook re-injects the summary and a reminder to grep.

## Install

Needs Python 3.9+ and Claude Code. Nothing is downloaded.

1. Put `thread.py` on your `PATH` as `thread`:

   ```sh
   mkdir -p ~/.local/bin
   ln -s "$PWD/thread.py" ~/.local/bin/thread
   ```

   `~/.local/bin` must be on your `PATH`; `thread --help` must work in a new terminal.

   On Windows, copy `thread.py` somewhere and add a `thread.cmd` on `PATH` that contains
   `@python C:\path\to\thread.py %*`.

2. Copy the skill:

   ```sh
   mkdir -p ~/.claude/skills && cp -r skill/thread ~/.claude/skills/
   ```

   The result must be `~/.claude/skills/thread/SKILL.md`.

3. Merge the `hooks` block of [hooks.json](hooks.json) into `~/.claude/settings.json`. If you already
   have hooks for an event, append the whole `{ ... }` group from `hooks.json` to that event's list.
   For `SessionStart` it must stay a group of its own with `"matcher": "compact"`.

4. Optional: allow the command, so each call does not ask for permission. Add `"Bash(thread:*)"` to
   `permissions.allow` in `~/.claude/settings.json`.

Without step 3, capture happens only when a `thread` command runs, and nothing is re-injected after
compaction.

`thread` must be on the `PATH` of the non-interactive shell that runs hooks, not only of your
terminal. If the hooks do not fire, start a new session; `/hooks` must list the four entries.

### Check the install

The check must be made from outside the session, because a `thread` command run by the agent
captures by itself and would hide a missing hook.

1. In a new Claude Code session, ask for `thread new install check`.
2. In a separate terminal, run `thread grep --count . -t install-check` and note the number.
3. In the session, send one ordinary message (for example "say hello") and wait for the reply. Do
   not ask for any `thread` command.
4. Run the command from step 2 again. The number must be higher. If it is not, the Stop hook did
   not run: check that `thread` is on the `PATH` of the hook shell and that hooks are allowed.
5. `~/.threads/errors.log` must not exist. If it does, it holds the hook's traceback.
6. In the shell that runs hooks, `echo '{}' | thread hook; echo $?` must print `0`. Exit code 2
   from a hook makes Claude Code block the turn or the compaction, so it must never happen.
7. Remove the test thread: `rm -rf ~/.threads/install-check`.

### To check on a Windows work machine

None of this was run on Windows. Before relying on it there:

- Expect to need two wrappers. Hooks run in Git Bash when it is installed, and Git Bash does not
  resolve `thread` to `thread.cmd`: add an extensionless file named `thread` beside it that
  contains `#!/bin/sh` and `python "C:/path/to/thread.py" "$@" || exit 1`. The `|| exit 1`
  matters: with a wrong path Python exits with code 2, which Claude Code reads as "block". The
  agent's own commands may run in PowerShell, which uses `thread.cmd`.
- In PowerShell the `<<'EOF'` examples in the skill do not work. Pipe a here-string instead:
  `@'` / text / `'@ | thread note`. The permission rule for PowerShell is `PowerShell(thread *)`.
  Windows PowerShell 5.1 may turn non-ASCII characters in piped text into `?`.
- The SessionEnd hook has a 10-second limit in `hooks.json`. If Python starts slowly (antivirus
  scanning), raise it.
- Python may be `python` or `py`, not `python3`.
- The skill goes in `%USERPROFILE%\.claude\skills\thread\`, the hooks in
  `%USERPROFILE%\.claude\settings.json`.
- File modes do nothing on Windows; the folder has the permissions of your user profile.
- A managed policy may forbid user hooks. The tool still works without them (see above).

## Commands

| Command | Does |
|---|---|
| `thread new <title> [--kind K]` | Create a thread and bind this session. A session with no earlier thread is captured from its start. |
| `thread list [--all] [--kind K]` | List open threads, newest activity first. `*` marks the active one. |
| `thread open <id>` | Print the summary and what came after the last checkpoint; bind this session. A closed thread is shown read-only. A unique id prefix is enough. |
| `thread note <text>` | Append a note (text as arguments or on stdin). |
| `thread checkpoint` | Replace the summary (text as arguments or on stdin). Warns above 6000 characters, the amount re-injected after a compaction. |
| `thread grep <regex>` | Case-insensitive search of the log. `--count`, `--max N` (10, max 30), `--offset N`, `--context N` (1, max 3), `--all` for every thread. A page ends early at about 6000 characters; the footer gives the `--offset` of the first match not shown. Printed lines are clipped to 400 characters. Earlier `thread grep` calls are not searched. |
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

The log contains whatever your tools printed, including any secrets. Claude Code already keeps the
same transcripts under `~/.claude/projects`; treat `~/.threads` the same way.

## Limits

- Capture reads Claude Code's transcript files, whose format is not documented and may change.
- Only the main session is captured. A subagent's work appears as the prompt it was given and the
  report it returned.
- Capture runs when a turn ends, before compaction, at session end, and on `new`, `open` (of an
  open thread), `reopen`, `note`, `checkpoint`, `close`, `detach` and the first page of `grep`.
- The turn-end hook does not run when you interrupt a turn or the turn fails with an API error, and
  nothing runs when a session is killed. That turn is captured by the next hook or `thread`
  command in the same session, or not at all if the session is never used again.
- Thinking is stored only when the transcript holds its text. Current Claude Code leaves most
  thinking blocks empty.
- `thread grep` and `thread open` clip what they print (400 and 600 characters per line or entry).
  For the full text, read `~/.threads/<id>/log.txt` at the `thread:line` that grep shows.
- With `--all`, pages are numbered across threads in id order. If another session adds matching
  entries between two pages, some matches can appear twice; none is skipped.
- Claude Code writes the transcript asynchronously, so a capture can miss the newest lines. The next
  capture takes them.
- A transcript line the tool cannot read is skipped and recorded as an `event` entry.
- Claude Code itself stores a very large tool output in the transcript as a short preview plus a
  file path. The log gets what the transcript holds, so it has only the preview.
- The output of `thread grep` is not stored: the call is logged and its result is replaced by a
  marker, because it only repeats the log. This applies to any shell command that runs
  `thread grep`, alone or chained (`cd x && thread grep y`), so other output of that command is
  lost with it. A command that only mentions the words (a commit message) is not affected.
- Inside an entry, unusual line separators (form feed, U+2028, CR) are stored as newlines, and a
  body line that starts with `=== ` gains a leading space.
- A forked or resumed session's transcript repeats its parent's lines; only lines carrying the
  session's own id are captured.
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
