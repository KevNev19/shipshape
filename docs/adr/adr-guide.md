# ADR Guide

Decision records for shipshape. One decision per file, `NNNN-kebab-title.md`.

Format (parseable by adr-tools):

```
# NNNN — Title

Date: YYYY-MM-DD

## Status

Accepted        <- single keyword body: Accepted | Proposed |
                   Superseded by [ADR-NNNN](NNNN-x.md) | Deprecated | Rejected

## Context
## Decision
## Consequences
```

Rules:

- Never edit a decided ADR's reasoning — write a superseding ADR and flip
  the old one's Status.
- Status means the decision is settled, not that it is built. Partial
  implementation notes go in Consequences.
- Cross-reference other ADRs as markdown links, never bare text.
- This folder holds records only; keep guides (like this one) clearly named
  so tooling that indexes `NNNN-*.md` stays clean.
