# Threads

Long-lived units of work for a coding agent, kept as a searchable record across many sessions.

## Language

**Thread**:
A long-lived unit of work (a project, a feature, an idea, a bug) with exactly one log and one summary. Threads are flat: none contains another.
_Avoid_: Task, ticket, conversation, project (a project is only a kind)

**Session**:
One Claude Code conversation. A session may work on several threads in turn, and several sessions may work on one thread.
_Avoid_: Chat, run, thread

**Active thread**:
The thread a session is bound to at this moment; a session has at most one.
_Avoid_: Current thread, open thread ("open" is a status)

**Bind**:
To make a thread the active thread of a session.
_Avoid_: Attach, join, select

**Detach**:
To leave a session with no active thread, so that nothing more of it is captured.
_Avoid_: Unbind, pause

**Log**:
The append-only record of a thread. The tool never edits, shortens or removes anything in it.
_Avoid_: History, transcript (the transcript belongs to a session)

**Entry**:
One record in the log.
_Avoid_: Line, message

**Entry type**:
What an entry records. The types are: a user message (`user`), an assistant message (`assistant`), thinking (`thinking`), a tool call (`tool_use`), a tool result (`tool_result`), a notice or message from another agent (`subagent`), a notice from a background command (`notification`), a summary Claude Code wrote at a compaction (`compaction`), a note (`note`), a checkpoint (`checkpoint`), and an event: the thread was created, closed or reopened, or capture skipped something (`event`).
_Avoid_: Kind (a kind belongs to a thread), role

**Capture**:
The entries taken from a session's transcript without the agent's involvement. Text is taken as the transcript holds it; images are recorded only as a marker, and lines that Claude Code injects are left out.
_Avoid_: Recording, sync

**Fork**:
A session that Claude Code starts as a copy of another session. It has its own id and no active thread.

**Compaction**:
Claude Code's replacement of a session's earlier context by a summary. The summary is logged; the thread's own summary is put back into context afterwards.

**Call id**:
The identifier that a tool call and its result share, shown in both entry headers.

**Backfill**:
Capture of the part of a session that happened before it was bound to its first thread. Only creating a thread backfills; opening one does not.

**Note**:
An entry written on purpose by the agent or the owner.
_Avoid_: Comment, memo

**Summary**:
The current statement of where a thread stands; the only part read in full on resume.
_Avoid_: State, digest

**Checkpoint**:
The act of replacing the summary, and the entry that act leaves in the log. Every replaced summary remains there.
_Avoid_: Save, snapshot

**Kind**:
A free-text label on a thread (project, feature, idea, bug). It carries no behaviour.
_Avoid_: Category, tag, entry type

**Status**:
Whether a thread is open or closed; there are no other statuses. A closed thread has a final summary, by convention with the outcome on its first line; it stays searchable and can be reopened.
_Avoid_: State, done, archived, resolved
