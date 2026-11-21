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

**Log**:
The append-only, complete record of a thread. Nothing in it is ever edited or removed.
_Avoid_: History, transcript (the transcript belongs to a session)

**Entry**:
One record in the log.
_Avoid_: Line, message, event

**Capture**:
The entries taken from a session's transcript without the agent's involvement.
_Avoid_: Recording, sync

**Backfill**:
Capture of the part of a session that happened before it was bound to its first thread.

**Note**:
An entry written on purpose by the agent or the owner.
_Avoid_: Comment, memo

**Summary**:
The current statement of a thread's state; the only part read in full on resume.
_Avoid_: Status, digest

**Checkpoint**:
The act of replacing the summary. Every replaced summary remains in the log.
_Avoid_: Save, snapshot

**Kind**:
A free-text label on a thread (project, feature, idea, bug). It carries no behaviour.
_Avoid_: Type, category

**Open / Closed**:
The two states of a thread. A closed thread has a final summary whose first line states the outcome; it stays searchable and can be reopened.
_Avoid_: Done, archived, resolved
