# 0009 — Lightweight durable change intent

Date: 2026-08-13

## Status

Proposed

## Decision

Shipshape offers — and never mandates — a four-field, in-repo intent
artifact for non-trivial changes:

1. A managed source template `templates/docs/change-intent.md.tmpl` renders
   to `.sdlc/templates/change-intent.md` (pillar `process`, ask-if-drifted,
   no feature flag: the template is always available, use is optional).
2. A stdlib helper `scripts/intent.py create <repo> --slug <slug>` validates
   exactly four short fields — problem, constraints, non-goals, acceptance
   checks — refuses to overwrite, and writes
   `docs/changes/YYYY-MM-DD-<slug>.md`. Created intent files are user-owned:
   shipshape never revises one after acceptance.
3. A new `skills/shipshape-intent` skill conducts the four questions in the
   kit's plain-language voice, recommends **no artifact** for trivial
   changes (typo-class), and invokes the helper only after showing the file
   and getting a yes.
4. The PR and task templates link to an intent file when one exists rather
   than duplicating it; findings-first review
   ([ADR 0007](0007-findings-first-review.md)) reports conformance against
   it, or states plainly that no intent artifact was warranted.

The trivial-change escape hatch is the load-bearing rule: any flow that
makes a typo fix require paperwork violates this ADR. Intent may be edited
freely until implementation begins; afterwards, changes to it are appended
as dated amendments, never silent rewrites.

## Context

Tier 2 evidence supports intent capture ("an agent will happily build the
wrong thing fast"; verification→validation shift: agents check
conformance cheaply, humans must decide whether the target was right). The
Tier 3 counter-evidence is equally binding on the shape: Böckeler found
spec-driven tools produce throwaway spec-first ceremony, and the Scott
Logic head-to-head measured 2,500+ lines of markdown and 3.5 hours of
review doing ~10x slower what plain prompting did with no bug reduction.
Four short fields is the deliberate maximum. Full analysis: gap 7 of
[0002](../research/0002-shipshape-vs-ai-native-sdlc.md).

## Consequences

- The kit gains its first per-change durable artifact, answering the SDD
  test from the research ("what happens to the spec after merge?") with:
  it stays in `docs/changes/`, versioned, and review reads it.
- Cost is bounded by design: four fields, optional, trivial-change escape.
  If pilot use shows median authoring time above a few minutes or skipped
  artifacts on most non-trivial changes, the shape is wrong — simplify or
  withdraw rather than enforce.
- Helper is stdlib + one JSON object ([ADR 0002](0002-python-stdlib-scripts.md));
  the skill sequences and translates, holding no logic; templates are
  token-only and the created files are explicitly outside the drift
  contract's managed set ([ADR 0003](0003-token-substitution-templates.md)).
- A seventh skill slightly widens the kit's surface; it ships
  `disable-model-invocation: true` like the other mutating skills.
