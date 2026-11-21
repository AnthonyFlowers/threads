# Thread data lives in ~/.threads, never in a repository

Threads span repositories and their logs hold complete session transcripts, which at work can include
anything a tool printed. We keep all thread data in one machine-local directory (`~/.threads`, mode 0600)
so it can never be committed by accident and one thread can follow work across codebases. The cost is
accepted: no sharing with teammates through git and no sync between machines; `thread export` is the only
way a thread's content leaves the machine.

## Considered options

- Per-repo `.threads/`, gitignored: keeps threads beside the code, but splits a cross-repo thread and relies on every repo's ignore file.
- Per-repo, committed: shareable, but puts raw transcripts in git history.
