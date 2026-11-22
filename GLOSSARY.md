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
The append-only record of a thread. Nothing in it is ever edited, shortened or removed.
_Avoid_: History, transcript (the transcript belongs to a session)

**Entry**:
One record in the log.
_Avoid_: Line, message, record

**Entry type**:
What an entry records: a user or assistant message, thinking, a tool call, a tool result, a note, a checkpoint, or an event (the thread was created, closed or reopened, or capture skipped something).
_Avoid_: Kind (a kind belongs to a thread), role

**Capture**:
The entries taken from a session's transcript without the agent's involvement. Text is taken as the transcript holds it; images and the tool's own search output are recorded only as a marker.
_Avoid_: Recording, sync

**Backfill**:
Capture of the part of a session that happened before it was bound to its first thread.

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
