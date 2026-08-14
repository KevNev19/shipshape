# 0007 — Findings-first semantic review

Date: 2026-08-13

## Status

Accepted

## Decision

All three review surfaces — `/shipshape-review`, the generated
`.github/agents/reviewer.md`, and `.github/copilot-instructions.md` — stop
narrating the diff and start reporting verified findings against intent.

The shared contract, recorded once in
`skills/shipshape-review/references/finding-contract.md` and mirrored into
the generated briefings, orders every review as:

1. Intent: available or missing (linked when a change-intent artifact or
   issue exists).
2. Verified findings, ordered by severity, each carrying its evidence (a
   check result or file/line), its plain-language consequence, and one next
   action.
3. Intent conformance: does the change do what was asked, and only that.
4. Material uncertainties: what the reviewer could not verify, stated
   plainly — "no verified findings" never means "no risk."
5. The existing verdict, unchanged and exact: "Looks safe to merge" /
   "Needs attention first: X" / "Do not merge: X". The two automatic
   escalations survive verbatim: secrets in the diff are an automatic
   "Do not merge," and red checks can never be called safe.

The reviewer still reads the full diff internally; it stops reciting it.

## Context

The strongest review evidence in [0001](../research/0001-ai-native-sdlc.md)
is Tier 1: the 8.1M-PR LinearB dataset locates the failure in reviewer
pickup queues, and Finster's sampling-rate argument shows human review
degrades past ~400 changed lines while adding blocking reviewers does not
fix the mismatch. The supported conclusion is to spend scarce human
attention on verified findings and intent-conformance rather than raw
diffs. Shipshape's current rubric is disciplined but diff-organized. Full
analysis: gap 4 of [0002](../research/0002-shipshape-vs-ai-native-sdlc.md).

## Consequences

- Human merge authority is untouched — this changes what the human reads,
  not who decides ([ADR 0004](0004-github-agents-support.md) stands).
- The verdict strings and their guarantees are invariant, so consumer
  expectations and any tooling keyed on them do not break.
- The three surfaces must change together in one release; a split contract
  (skill reporting findings, generated reviewer narrating diffs) would be
  worse than either alone.
- Intent conformance degrades gracefully before
  [ADR 0009](0009-lightweight-change-intent.md) exists: when no intent
  artifact or issue is found, the review says so instead of guessing.
- Rejection criteria: if findings-first reports measurably hide behavioral
  context the old summary carried (merges that surprise their author), the
  contract gains a one-paragraph behavior summary rather than reverting.
