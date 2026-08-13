# 0006 — Scheduled stewardship for consumer repositories

Date: 2026-08-13

## Status

Accepted

## Decision

Shipshape renders a self-contained health check into consumer repositories
and runs it on a schedule, so drift is noticed without anyone asking.

1. A new template `templates/scripts/doctor.py.tmpl` renders to
   `.sdlc/scripts/doctor.py` (mode 755). It is stdlib-only, embeds
   `{{KIT_VERSION}}`, and vendors the few hashing/state helpers it needs —
   it must not import the plugin's `render.py`, because consumers do not
   have the plugin's scripts.
2. A new template `templates/github/workflows/shipshape-doctor.yml.tmpl`
   renders to `.github/workflows/shipshape-doctor.yml`: weekly cron plus
   `workflow_dispatch`, permissions `contents: read` and `issues: write`,
   runs the rendered doctor, writes the translated scorecard to the job
   summary, and opens or updates exactly one issue only on WARN or FAIL.
3. Both manifest entries use pillar `workflows`, overwrite policy
   `ask-if-drifted`, and a new `scheduled_health` feature flag, default on.
   Disabling goes through the customize skill's consequence sentence
   ("nobody will be told when a protection quietly disappears").
4. `scripts/doctor.py` (plugin side) gains a `scheduled health check`:
   PASS when both managed files exist and the workflow has a schedule,
   WARN when the feature is deliberately off, FAIL when the feature is on
   but either file is missing.

## Context

The kit's drift sensor runs only when a human invokes `/shipshape-doctor`.
The only scheduled controls shipped to consumers are CodeQL's weekly cron
and Dependabot — neither checks whether shipshape's own protections are
still present and connected. The harness-engineering literature identifies
this as the feed-forward-only failure mode: rules are encoded but nothing
learns whether they still hold. Tier 2 design pressure, plus the named gap
in [0001](../research/0001-ai-native-sdlc.md) §6; full analysis in gap 2 of
[0002](../research/0002-shipshape-vs-ai-native-sdlc.md).

## Consequences

- This is the kit's first distribution of executable Python to consumers.
  The rendered doctor becomes a second implementation to keep in sync with
  the plugin's; a meta-test must assert the two agree on check names and
  semantics, and version skew is surfaced by the existing kit-version check.
- Issue-writing is new outward behavior; capping it at one deduplicated
  issue prevents notification fatigue. The workflow must degrade to a job
  summary when `issues: write` is unavailable.
- Weekly cron cost is one short Python job — negligible against the CodeQL
  baseline the kit already ships.
- Stdlib-only and JSON-only stdout are preserved
  ([ADR 0002](0002-python-stdlib-scripts.md)); both artifacts are token-only
  and never-clobber ([ADR 0003](0003-token-substitution-templates.md)); the
  job reports and never merges ([ADR 0004](0004-github-agents-support.md)).
- Rejection criteria: if the self-contained doctor cannot be kept honestly
  in sync with the plugin's (drift between the two produces contradictory
  scorecards), ship a thinner presence-only checker instead.
