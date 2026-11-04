# Changelog

All notable changes to shipshape are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- A launch film on the marketing site, directly under the hero, and a
  poster in the README that links to it. The film loops muted while it is
  on screen, and stays on the poster when the visitor prefers reduced
  motion. Music is Happy Beats / Business Moves vol. 12 by Sascha Ende
  (CC BY 4.0). Sound effects are by Kenney (CC0). Pull requests that
  change the site run a Lighthouse check for performance, accessibility,
  best practices and layout shift.
- This changelog.
- An optional GitHub Projects board (`features.project_board`, ADR 0014).
  It is off unless asked for. Setup only adds missing fields and open
  issues, and the weekly health job can place its issue on the board.
- An optional commit label (`features.provenance_labels`). It checks a
  self-declared `Agent-Assisted-By: Tool Name` line and still accepts a
  commit that leaves the line off. The label is context, not a safety
  check. Pull requests also ask an optional "How was this made?" question.
- An optional test-quality warning (`features.test_quality`). When it is
  on, doctor warns about a Python test with no recognized assertion. The
  warning does not fail the scorecard or block a merge, and it does not
  run mutation testing.
- An optional progressive-delivery page (`features.progressive_delivery`).
  It is a checklist for a feature flag and a canary. It does not deploy
  the project, roll a release back, or replace review.

### Fixed

- The Lighthouse check uses the worst of its three runs, so one good run
  cannot hide a run that misses a budget. Performance must stay at or
  above 0.80 on every run.
- The launch film pauses when it leaves the screen, including after the
  visitor pressed play. A play or pause the page starts is counted on its
  own, so the page does not treat its own pause as the visitor pausing.
- CodeQL no longer sees a bad HTML-tag filter in the site test. The test
  reads the site's inline scripts with the HTML parser.
- The review-gate tests ask `git hash-object` for a blob id. The config
  field `secret_guard` is part of that blob, and hashing those bytes with
  `hashlib.sha1` is the weak-hash finding.
- The weekly security and quality report reads Dependabot alerts with the
  workflow token (`vulnerability-alerts: read`). Secret scanning still needs
  `ACTIONS_PAT`, and a denial now says so instead of a bare API failure.
- That report updates one rolling issue titled "Security & quality report"
  instead of opening a new issue every week.

## [0.4.0] - 2026-10-18

The 0.4.0 version bump was not given its own git tag. This section is what
`main` carries at version 0.4.0, including the fixes that landed after the
bump and before the next release.

### Added

- Check detection, proving, and running (`scripts/checks.py`, ADR 0012),
  including Node's built-in test runner.
- A test-integrity diff check that reports weakened or removed tests.
- Artefact review profiles (ADR 0013), so review reads the change through
  the lens that matches the files.

### Fixed

- Tests a history audit found weakened were restored.
- Skill files were trimmed so a marketplace scanner stopped flagging them.

## [0.3.0] - 2026-10-13

Prepared on `main`. No git tag was published for 0.3.0. The version number
moved from 0.2.1 straight to 0.3.0 once the work below had landed.

### Added

- Codex host support and the orchestrate skill.
- Marketing site on GitHub Pages, and README art that matches it (ADR 0011).
- Scheduled health check for consumer repositories (ADR 0006). One issue is
  updated when something needs attention.
- Tiered review that can auto-merge a low-risk change (ADR 0008).
- Findings-first review (ADR 0007).
- A guard for agent and editor control files (ADR 0005).
- Lightweight change-intent capture (ADR 0009).
- Source-bound automation and the control policy (ADR 0010).
- Doctor checks for unused settings and test retries.
- Test-quality and verification-cost checks.

### Changed

- Setup, the secret guard, merge, and release were hardened, including fixes
  found by the 2026-08-23 end-to-end sweep.

## [0.2.1] - 2026-08-10

### Added

- Copilot code review instructions.
- A Rust detection fixture.

## [0.2.0] - 2026-08-10

### Added

- GitHub agent surface (ADR 0004): custom agents and Copilot instructions.

## [0.1.0] - 2026-08-10

### Added

- First kit: repository scanner, template renderer with a drift guard,
  `shipshape-init`, doctor, secret guard, CI, CodeQL, Dependabot, the release
  workflow, and the setup skills.

0.3.0 and 0.4.0 were not tagged, so they have no release-to-release compare URL.

[0.2.1]: https://github.com/KevNev19/shipshape/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/KevNev19/shipshape/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/KevNev19/shipshape/releases/tag/v0.1.0
