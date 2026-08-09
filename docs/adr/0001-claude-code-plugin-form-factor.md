# 0001 — Distribute shipshape as a Claude Code plugin

Date: 2026-08-10

## Status

Accepted

## Context

Shipshape must be installable into any existing git repository by people who
are not software engineers, and customization must start from working
defaults. Candidate form factors: a GitHub template repository (cannot
retrofit existing repos), a standalone CLI installer (a second toolchain to
maintain, no conversational onboarding), or a Claude Code plugin.

## Decision

Ship as a Claude Code plugin in a self-hosting marketplace repository.
Consumers enable it with two entries in `.claude/settings.json`
(`extraKnownMarketplaces` + `enabledPlugins`) — no vendored code. Skills
locate bundled scripts via `${CLAUDE_PLUGIN_ROOT}`. Onboarding is itself a
skill (`/shipshape-init`) that writes plain files into the target repo, so
the result works without the plugin present.

## Consequences

- Non-engineers get a conversational front door; the interview and all
  output follow a shared plain-English voice contract.
- Everything written into a target repo is inert standard tooling (GitHub
  workflows, git hooks, markdown) — removing the plugin removes the setup
  experience, not the setup.
- Other AI hosts are supported later by thin adapters, because all policy
  written into target repos lives in a model-neutral harness document.
