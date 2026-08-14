# 0008 — Tiered review authority behind green gates

Date: 2026-08-13

## Status

Accepted

## Decision

This ADR, when accepted, supersedes the universal human-merge rule of
[ADR 0004](0004-github-agents-support.md) for exactly two narrow classes,
behind an opt-in `tiered_review` feature (default off, PR-style repos only):

1. Documentation-only changes outside security, process, and agent-control
   paths (the [ADR 0005](0005-agent-control-files-security-sensitive.md)
   list, plus `.github/**` and `.sdlc/**`).
2. Authenticated dependency-bot patch updates that modify only an existing
   manifest and its lockfile.

For those classes only, a rendered workflow
(`.github/workflows/low-risk-automerge.yml`, from a new template) enables
GitHub auto-merge once every required check is green. It triggers on
`pull_request_target` but never checks out or executes the proposed code:
it inspects changed paths and check states via the API only. Everything
else — new dependencies, scripts, workflows, security files, agent
controls, failing or absent checks, unknown paths — remains human-merged.
Break-glass use of the workflow outside its classes is labeled,
actor-stamped, and auditable. A doctor check (`tiered review gates`) FAILs
when auto-merge is enabled without every required check enforced.

## Context

Tier 1 evidence (LinearB queueing, Finster's sampling rate) shows the
human gate is where AI-era volume piles up; Tier 2 attention evidence
(Tornhill; Faros cognitive-load telemetry) shows adding more human review
contexts is not free. The research's own judgment in
[0001](../research/0001-ai-native-sdlc.md) §6 kept "automation proposes,
CI checks, a human merges" for small teams and called auto-merge for
docs/deps "plausible ADR material, not policy yet." This is that ADR. Full
analysis: gap 6 of [0002](../research/0002-shipshape-vs-ai-native-sdlc.md).

## Consequences

- Sequencing: this ships only after
  [ADR 0007](0007-findings-first-review.md) is in operation, so what humans
  stop reviewing is exactly what findings-first review already covers with
  deterministic gates.
- The blast radius of a wrong auto-merge is bounded by the path classes:
  prose and patch-level pins, never executable surface. Dependency-bot
  identity must be verified by login, not branch name.
- `pull_request_target` is used strictly API-side; the workflow never runs
  contributed code. This is the single most safety-critical implementation
  constraint and gets its own regression test.
- Consumers who never enable the flag see zero behavior change; the
  customize skill's consequence gate applies on enable, not disable
  ("changes matching these two classes will merge without a person").
- Cloudflare's published 0.6% break-glass rate is the calibration
  benchmark: materially higher sustained break-glass use means the classes
  are wrong and the feature should be narrowed or withdrawn.
- Rejection criteria: any incident in which a change outside the two
  classes auto-merged, or a dependency-bot impersonation lands, withdraws
  the feature pending a redesign — not a patch.
