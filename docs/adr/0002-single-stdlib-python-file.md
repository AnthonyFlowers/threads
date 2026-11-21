# One Python file, standard library only, no network

The tool must be usable on a restricted work machine where external tools and services are not allowed.
It is therefore a single Python 3 file with no third-party packages and no network access, so it can be
read in full for a security review and installed by copying one file. This rules out conveniences that
would otherwise be obvious (a database or embedding index for recall, a packaging/install step, a model
call to write summaries); recall is regex search over plain text, as in the GrepMem paper.

## Considered options

- Go static binary: no runtime needed, but a binary is harder to get approved and cannot be reviewed by reading it.
- Python with packages from an internal registry: more features, but every dependency is another approval.
