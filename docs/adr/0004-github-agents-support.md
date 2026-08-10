# 0004 — Support GitHub's agent surface via generated adapters

Date: 2026-08-10

## Status

Accepted

## Context

GitHub's agent surface (Copilot coding agent and third-party agents in Agent
HQ) works from issues and tasks into pull requests, reading `AGENTS.md` for
repository instructions, `.github/agents/*.md` for custom agent profiles,
and `.github/workflows/copilot-setup-steps.yml` for workspace setup. Cloud
agents never run local git hooks, so the commit-time secret guard alone
would not cover agent-authored changes. ADR 0001 anticipated other hosts as
thin adapters over the model-neutral harness doc.

## Decision

Shipshape generates the GitHub agent surface from the same config that
drives everything else:

- `AGENTS.md` — always written: a ≤30-line adapter pointing at
  `docs/sdlc/harness.md` ("mirrored only by reference"), plus universal
  agent rules (honest test reporting, PRs through the checks, no secrets).
- `.github/workflows/copilot-setup-steps.yml` — per-language variants,
  gated by `features.github_agents`.
- `.github/agents/reviewer.md` — a custom reviewer agent encoding the same
  verdict rules as `/shipshape-review` (red CI never "looks safe"), gated by
  `features.github_agents`.
- `.github/workflows/secret-scan.yml` — the secret guard re-run in CI via a
  new `--range A..B` mode, gated by `features.secret_guard`, closing the
  coverage gap for changes that never touch a local commit hook.

Agent-authored pull requests follow the existing automation lane: automation
proposes, CI checks, a human merges.

## Consequences

- Any agent GitHub points at an initialized repo inherits its working
  agreement, and its output flows through the same gates as human work.
- The custom-agent file format is still evolving upstream; these are
  managed files, so format changes ship as template updates and the drift
  machinery handles locally-edited copies.
- The reviewer briefing intentionally duplicates the plugin's review rubric
  in condensed form — the target repo copy must be self-contained.
