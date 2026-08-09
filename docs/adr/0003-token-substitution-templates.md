# 0003 — Templates use {{TOKEN}} substitution, variants instead of logic

Date: 2026-08-10

## Status

Accepted

## Context

Shipshape renders files into target repos parameterized by detected stack
and user choices. A real template engine (Jinja et al.) would add a
dependency (against ADR 0002) and invite conditional logic inside templates,
which is hard to test and hard for users to read once rendered.

## Decision

Templates contain only `{{TOKEN}}` placeholders substituted by `render.py`.
No conditionals, no loops. Where output must differ structurally (CI per
language), there is one template variant per case, selected by `when`
conditions in `templates/manifest.json`. `render.py` refuses to write any
output that still contains a token, and treats an empty token value as an
error rather than rendering a blank into a command or branch name.

Drift protection: `.sdlc/state.json` records the sha256 of every file as
written. A file whose hash no longer matches was edited by the user and is
reported as a conflict — never overwritten without an explicit per-file
`--force`. Files with `overwrite_policy: write-once` (the design doc) are
never regenerated at all.

## Consequences

- More template files, zero template logic; each variant is independently
  testable and reads exactly like the file it produces.
- Every rendered artifact carries a `managed-by: shipshape vX.Y` header and
  a plain-English "what is this / safe to edit?" comment.
- Cross-version upgrades of drifted files are ask-per-file in v1; the state
  file records `kit_version` per file so a smarter merge can come later.
