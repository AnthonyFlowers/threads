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
  thinking, tool calls and tool outputs, with no text truncated. Images are logged as `[image]`;
  Claude Code's own system lines and attachments are not captured.
- The agent writes notes and, at milestones, a checkpoint that replaces `summary.md`.
- A later session runs `thread open`, reads the summary, and uses `thread grep` for the details.
- After Claude Code compacts the context, a hook re-injects the summary and a reminder to grep.

## Install

Needs Python 3.9+ and Claude Code. Nothing is downloaded.

1. Put `thread.py` on your `PATH` as `thread`:

   ```sh
   chmod +x thread.py
   ln -s "$PWD/thread.py" ~/.local/bin/thread
   ```

   On Windows, copy `thread.py` somewhere and add a `thread.cmd` on `PATH` that contains
   `@python C:\path\to\thread.py %*`.

2. Copy the skill:

   ```sh
   mkdir -p ~/.claude/skills && cp -r skill/thread ~/.claude/skills/
   ```

   The result must be `~/.claude/skills/thread/SKILL.md`.

3. Merge the `hooks` block of [hooks.json](hooks.json) into `~/.claude/settings.json`. If you already
   have hooks for an event, add the `thread hook` entry to that event's list.

4. Optional: allow the command, so each call does not ask for permission. Add `"Bash(thread:*)"` to
   `permissions.allow` in `~/.claude/settings.json`.

Without step 3, capture happens only when a `thread` command runs, and nothing is re-injected after
compaction.

`thread` must be on the `PATH` of the non-interactive shell that runs hooks, not only of your
terminal. Hooks are read when a session starts, so start a new session after step 3.

### Check the install

In a new Claude Code session:

1. Ask for `thread new install check`, then send one more message.
2. `thread grep --count .` must print a number that rises after each turn.
3. `~/.threads/errors.log` must not exist. If it does, it holds the hook's traceback.
4. Remove the test thread: `rm -rf ~/.threads/install-check`.

### To check on a Windows work machine

None of this was run on Windows. Before relying on it there:

- Claude Code on Windows usually runs commands in Git Bash, which does not resolve `thread` to
  `thread.cmd`. If `thread` is not found, add an extensionless file named `thread` beside it that
  contains `#!/bin/sh` and `exec python "C:/path/to/thread.py" "$@"`.
- If commands run in PowerShell instead, the `<<'EOF'` examples in the skill do not work; pipe the
  text to the command instead.
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
| `thread checkpoint` | Replace the summary (text as arguments or on stdin). |
| `thread grep <regex>` | Case-insensitive search of the log. `--count`, `--max N` (10, max 30), `--offset N`, `--context N` (1, max 3), `--all` for every thread. A page ends early at about 6000 characters; the footer gives the `--offset` of the first match not shown. |
| `thread detach` | Stop capturing this session. |
| `thread close` | Close with a final summary (arguments or stdin). The log is kept. |
| `thread reopen <id>` | Reopen a closed thread and bind this session. |
| `thread export <id>` | Print the summary and all notes as markdown. |
| `thread hook` | Hook entry point; reads Claude Code's hook JSON on stdin. |

`note`, `checkpoint`, `close` and `grep` use the session's active thread; `-t <id>` names another.
Put `-t` before the text: everything after the first word of text is taken as text. Use stdin for
text with quotes, backticks or `$`.

## Data

```
~/.threads/
  <id>/meta.json     title, kind, status, created, cwd
  <id>/log.txt       append-only; each entry starts "=== <time> <session> <entry type> [tool] ==="
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
- Capture runs when a turn ends, before compaction, at session end, and on `new`, `open`, `reopen`,
  `note`, `checkpoint`, `close`, `detach` and `grep`. A session killed mid-turn loses that turn's
  capture until a later hook or command in the same session.
- Claude Code writes the transcript asynchronously, so a capture can miss the newest lines. The next
  capture takes them.
- A transcript line the tool cannot read is skipped and recorded as an `event` entry.
- A session that gets a new session id (for example after `/clear`) is not bound; run `thread open`
  again.
- Every `thread grep` call and its output are captured too, so a repeated search also matches its
  own earlier runs.
- Search is lexical. If you cannot guess a word that was used, you will not find the entry.

## Not in v1

Each of these was considered and left out. Add one when its trigger shows up.

| Left out | Why | Add it when |
|---|---|---|
| Secret redaction | Scanning is unreliable and the same text is already in Claude Code's transcripts. | Logs must leave the machine, or policy requires it. |
| Truncation of long tool outputs | The point of the pattern is a lossless log. | Disk use becomes a problem. |
| Compressing or archiving closed threads | Plain files are simpler to search and inspect. | `~/.threads` grows past a few GB. |
| Plugin packaging | Work may block plugin marketplaces; three manual steps are enough. | Several people install it. |
| An install command | Code that edits `settings.json` is a risk for little gain. | The manual steps cause errors. |
| More states (paused, blocked) | Open and closed cover the lifecycle; the summary says the rest. | `thread list` cannot answer "what is waiting". |
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
