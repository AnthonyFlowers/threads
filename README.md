# threads

A CLI and Claude Code skill that give a coding agent **threads**: long-lived units of work (a project,
a feature, an idea, a bug) that survive across sessions.

The design follows GrepMem, ["Forget Freely, Grep Later"](https://arxiv.org/abs/2611.25123): keep an
append-only plain-text log of the session, keep one summary in context, and recall details with
case-insensitive regex search. No index, no embeddings, no database. The grep limits (10 matches per
page, at most 30; 1 context line, at most 3; about 6,000 characters per page) are the paper's, and
so is the listing of matches grouped under their entry with merged context. The main differences:
the paper's agent writes its summary at every compaction and may grep only after the first one,
while here the summary is a checkpoint the agent writes by hand and grep is always available;
matches are listed newest first (the paper: oldest first); and entry headers and tool-call inputs
are searched as well as the text. The paper tested one 9B model, before and after RL training, on
single-episode benchmarks, not coding agents or work across sessions. `docs/LOG.md` has a
mechanism-by-mechanism comparison and a recall test on real transcripts.

- One Python 3 file, standard library only, no network access.
- All data in `~/.threads/` (directories mode 0700, files 0600), never in a repository.
- Terms are defined in [GLOSSARY.md](GLOSSARY.md); decisions in [docs/adr/](docs/adr/).

## How it works

- `thread new` or `thread open` binds the current Claude Code session to a thread.
- Hooks append the session transcript to that thread's `log.txt`: user and assistant messages,
  thinking, tool calls and tool results, as the transcript holds them and with nothing cut by this
  tool. Reports handed back by subagents and Claude Code's own compaction summaries are logged
  under their own entry types. Images are logged as `[image]`. Lines that Claude Code injects
  (system lines, attachments, skill instructions, reminders) are not captured. See
  [docs/LIMITS.md](docs/LIMITS.md) for the exceptions.
- The agent writes notes and, at milestones, a checkpoint that replaces `summary.md`.
- A later session runs `thread open`, reads the summary, and uses `thread grep` for the details.
- After Claude Code compacts the context, a hook re-injects the summary, says how many entries are
  newer than it, and reminds the agent to grep.
- When a session starts with no active thread in a folder where open threads were started (that
  folder or one below it), a hook prints one line naming them. The agent opens one only if you ask
  to continue that work. When a session with an active thread starts or resumes, the hook prints
  one line naming it.

## Install

Needs Python 3.9+ and Claude Code 2.1.132 or later (older versions do not tell the tool which
session it is in, so nothing is captured). Nothing is downloaded.

### macOS and Linux

1. Put `thread.py` on your `PATH` as `thread`:

   From this folder:

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

4. Optional: allow the command, so each call does not ask for permission. Add `"Bash(thread:*)"` to
   `permissions.allow` in `~/.claude/settings.json`.

Without step 3, capture happens only when a `thread` command runs, nothing is re-injected after
compaction, there is no reminder in a session without a thread, and `thread new` in a forked session
also captures the history copied from its parent.

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

   If only `py` works on your machine, write `py` instead of `python` in both wrappers.

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

- **Every new session, every `/clear` and every fork starts with no active thread.** Until you say
  "open the X thread" or "continue the X work" (or start a new one), that session is not captured.
  With the hooks installed, the agent is told in one line when open threads exist for the folder
  (the session's folder is the thread's, above it or below it); it will not open one unasked. To check, ask the agent for `thread list`: `*` marks the active
  thread. A `thread list` in your own
  terminal never shows `*`, because the terminal is not a Claude Code session.
- `thread list` shows open threads; `thread list --all` includes closed ones. To find a thread by
  what was said in it: `thread grep --all --count '<word>'`.
- A subagent runs `thread` commands with the main session's id. If it runs `thread new` or
  `thread open`, it moves the main session's capture to that thread.
- `thread note` from your own terminal needs `-t <id>`.
- **Upgrade:** replace `thread.py` and the skill folder with the new copies. Merge `hooks.json`
  again only when the release notes in `docs/LOG.md` say it changed.
- **Move to another machine:** copy `~/.threads` without its `.sessions` folder.
- **Clean up:** `.sessions` gains one small file per session that was ever bound or forked; delete the folder
  when no Claude Code session is running. `log.txt` is plain text and nothing indexes it, so you
  can edit it by hand, for example to remove a secret that was printed (line numbers cited in
  summaries then shift).

## Troubleshooting

| Sign | Likely cause |
|---|---|
| A command says the thread "was closed or removed by another session" | Another session closed, reopened or removed it; this session stopped being captured at that point. Open it again. |
| `thread list` (run by the agent) shows no `*` | New session, `/clear` or fork; or another session closed or removed the thread. Say "open the X thread" or "continue the X work". |
| `no Claude Code session id: nothing bound` | Claude Code older than 2.1.132, or the command was run outside Claude Code. |
| The count in "Check the install" does not rise | `thread` not on the `PATH` Claude Code was started with; hooks blocked by policy (`/hooks`); folder not trusted. |
| `thread list` prints "hook errors are recorded in ..." | Read `errors.log`; it holds the traceback. Delete it when solved. |
| The same lines appear twice in a log | A message arrived while a turn was running and Claude Code recorded it twice (both are kept by design), or Claude Code replaced a transcript file (see docs/LIMITS.md). |

## Commands

| Command | Does |
|---|---|
| `thread new <title> [--kind K]` | Create a thread and bind this session. A session with no earlier thread is captured from its start (the command says how many lines). The title becomes the id (lower case, at most 50 characters), so keep it to a few words. The kind is a free label and is case-sensitive. |
| `thread list [--all] [--kind K]` | List open threads, newest activity first. Each row: mark (`*` for the active thread), id, kind, status, date of the last log activity, title. The date is UTC, as in the log; a last line says so. |
| `thread open <id>` | Print the summary and what came after the last checkpoint (how many entries, by entry type, then the notes and latest messages); bind this session, capturing from now on. A closed thread is shown read-only. A unique id prefix is enough. |
| `thread note <text>` | Append a note (text as arguments or on stdin). Prints how many entries are newer than the last checkpoint, by entry type. |
| `thread checkpoint` | Replace the summary (text as arguments or on stdin). Warns above 6000 characters, the amount re-injected after a compaction. |
| `thread grep <regex>` | Case-insensitive search of the log, newest entry first (`--oldest` reverses). Matches are grouped under their entry's header; a result's header also shows the call that produced it. `--count` prints the total, then a breakdown by entry type when there is more than one (and by thread with `--all`). `--max N` (10, max 30), `--offset N`, `--context N` (1, max 3), `--type user,assistant,note` to search only those entry types, `--all` for every thread. A page ends early at about 6000 characters; the footer gives the `--offset` of the first match not shown. Context lines stay inside the matching entry. Printed lines are clipped to 400 characters. Earlier `thread grep` calls are not searched. Options go before a `--`. |
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
  <id>/meta.json     id, title, kind, status, created, cwd, uid, closes (after a close)
  <id>/log.txt       append-only; each entry starts "=== <time> <session id, 8 chars> <entry type> [tool] [call id] ==="
  <id>/summary.md    current summary
  .sessions/         which thread each session is bound to, and how much of it is captured;
                     a `.lock` file exists only while one command or hook is capturing
  errors.log         hook failures (a hook never blocks a session)
```

`THREADS_HOME` overrides the directory. `~/.threads` is always set to mode 0700; a folder named by
`THREADS_HOME` that already exists keeps its own permissions. To remove a thread: `rm -rf ~/.threads/<id>`. A session
bound to a removed or closed thread is treated as detached.

The log contains whatever your tools printed, including any secrets, and text from other
programs and web pages. Treat it as a record, not as instructions.

**Retention.** Claude Code deletes its own transcripts after 30 days by default. `~/.threads` keeps
its copy until you remove it; nothing is deleted automatically. If a retention rule applies to your
work, remove old threads yourself (`rm -rf ~/.threads/<id>`). `thread grep --all` reads every
thread, so text from one piece of work can reach a session working on another, and whatever a
command prints there is captured into that session's active thread (`thread export <other>` and
files read under `~/.threads` too).

## What it does not capture

- Sessions with no active thread. Every new session, `/clear` and fork starts that way; a hook
  line says so when open threads exist for the folder.
- What a session did before `thread open`. Only `thread new` claims the session so far.
- Subagents' internal steps (their final reports are captured), images, most thinking, and very
  large tool outputs (Claude Code keeps only a preview of those in its transcript).
- An interrupted or killed turn, until the same session is used again.
- Anything Claude Code changes in its undocumented transcript format without notice.

The full list, with the reasons, and the features left out of v1 are in
[docs/LIMITS.md](docs/LIMITS.md).

## Development

```sh
python3 -m unittest discover -s tests
```
