# Log

## Rig usage

| Date | Machine | What |
|---|---|---|
| 2026-11-21 | Mac | Design interview, v1 build, tests. No model host, no satellites. |

## Development

- 2026-11-21: Design settled in three interview passes (grill-me, grill-with-docs, grill-me). v1 built:
  `thread.py`, tests, skill, hooks snippet, glossary, ADR 0001 and 0002.

## Research notes

- Source: arXiv 2611.25123, "Forget Freely, Grep Later" (GrepMem). Taken from it: append-only log
  written by the harness, a summary that is also appended to the log, regex recall with pagination,
  count mode, context lines 1 (max 3), 10 matches per page (max 30), output cap about 6K characters,
  re-injection of the summary after compaction.
- Not from the paper (our own design): threads, kinds, open/closed, binding sessions to threads,
  backfill, notes, export.
- Read only through a fetch agent; the grep parameter defaults come from a model-written summary of
  the second half of the paper and were not checked against the PDF.
- Claude Code facts used: `CLAUDE_CODE_SESSION_ID` is set for Bash commands (seen in 2.1.316);
  transcripts are `~/.claude/projects/<dir>/<session>.jsonl` with `type` user/assistant and
  `message.content` blocks (text, thinking, tool_use, tool_result).
