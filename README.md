# threads

A CLI and Claude Code skill that give a coding agent **threads**: long-lived units of work (a project,
a feature, an idea, a bug) that survive across sessions.

The design follows GrepMem, ["Forget Freely, Grep Later"](https://arxiv.org/abs/2611.25123): keep an
append-only plain-text log of everything, keep one summary, and recall details with regex search. No
index, no embeddings, no database.

- One Python 3 file, standard library only, no network access.
- All data in `~/.threads/` (files mode 0600), never in a repository.
- Terms are defined in [GLOSSARY.md](GLOSSARY.md); decisions in [docs/adr/](docs/adr/).

## How it works

- `thread new` or `thread open` binds the current Claude Code session to a thread.
- Hooks append the session transcript to that thread's `log.txt`: user and assistant messages,
  thinking, tool calls and complete tool outputs. Images are logged as `[image]`.
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
   cp -r skill/thread ~/.claude/skills/
   ```

3. Merge the `hooks` block of [hooks.json](hooks.json) into `~/.claude/settings.json`. If you already
   have hooks for an event, add the `thread hook` entry to that event's list.

Without step 3 the tool still works, but the log holds only notes and checkpoints.

## Commands

| Command | Does |
|---|---|
| `thread new <title> [--kind K]` | Create a thread and bind this session. A session with no earlier thread is captured from its start. |
| `thread list [--all] [--kind K]` | List open threads, newest activity first. `*` marks the active one. |
| `thread open <id>` | Print the summary and what came after the last checkpoint; bind this session. A closed thread is shown read-only. A unique id prefix is enough. |
| `thread note <text>` | Append a note. |
| `thread checkpoint` | Replace the summary (text as arguments or on stdin). |
| `thread grep <regex>` | Case-insensitive search of the log. `--count`, `--max N` (10, max 30), `--offset N`, `--context N` (1, max 3), `--all` for every thread. Output is capped at about 6000 characters per page. |
| `thread detach` | Stop capturing this session. |
| `thread close` | Close with a final summary (arguments or stdin). The log is kept. |
| `thread reopen <id>` | Reopen a closed thread and bind this session. |
| `thread export <id>` | Print the summary and all notes as markdown. |
| `thread hook` | Hook entry point; reads Claude Code's hook JSON on stdin. |

`note`, `checkpoint`, `close` and `grep` use the session's active thread; `-t <id>` names another.

## Data

```
~/.threads/
  <id>/meta.json     title, kind, status, created, cwd
  <id>/log.txt       append-only; each entry starts "=== <time> <session> <kind> [tool] ==="
  <id>/summary.md    current summary
  .sessions/         which thread each session is bound to, and how much of it is captured
  errors.log         hook failures (a hook never blocks a session)
```

`THREADS_HOME` overrides the directory. To remove a thread: `rm -rf ~/.threads/<id>`.

The log contains whatever your tools printed, including any secrets. Claude Code already keeps the
same transcripts under `~/.claude/projects`; treat `~/.threads` the same way.

## Limits

- Capture reads Claude Code's transcript files, whose format is not documented and may change.
- Only the main session is captured. A subagent's work appears as the prompt it was given and the
  report it returned.
- Capture runs when a turn ends, before compaction, at session end, and on every `thread` command.
  A session killed mid-turn loses that turn's capture until a later hook or command in the same
  session.
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
| Locking between sessions | Appends are atomic per entry; the summary is last-writer-wins with every version in the log. | Duplicate or lost entries appear. |
| `thread delete` | `rm -rf ~/.threads/<id>` does it. | A retention rule needs an audited command. |
| `thread rename` | Ids are rarely typed in full; a prefix works. | A title turns out badly wrong often. |

## Development

```sh
python3 -m unittest discover -s tests
```
