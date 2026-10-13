# 0010 — Bind automation to source and expand control review

Date: 2026-09-09

## Status

Accepted

## Context

[ADR 0008](0008-tiered-review-authority.md) allowed documentation and
dependency-bot patch updates to enter persistent GitHub auto-merge after green
checks, with an automatic break-glass concept. Implementation review found
three mismatches: dependency and control metadata can execute or redirect
trusted tools; a green check name is not proof that the expected workflow ran
for the current commit; and persistent auto-merge outlives the observation that
made a pull request eligible.

GitHub's REST merge endpoint can condition the merge on the pull request head
SHA, but it cannot atomically freeze the base SHA observed during
classification. Strict server-side enforcement is therefore a required
boundary, not an optional duplicate. Direct-push trunk has a different
ordering constraint: its push starts CI, so adding a new required pre-landing
status would prevent the push that creates that status.

[ADR 0005](0005-agent-control-files-security-sensitive.md) also named only a
narrow first set of agent and editor paths. Native controls, nested instruction
files, plugin and skill metadata, workflow automation, and harness policy have
the same review consequence. The guard can identify paths and a short set of
executable JSON patterns, but it cannot prove that control content is safe.

Cloudflare reported that humans overrode its AI review approval for 0.6% of
merge requests. That is a different action and denominator from Shipshape
eligibility, so it is context rather than a threshold for this decision
([Cloudflare](https://blog.cloudflare.com/ai-code-review/)).

## Decision

### Automatic merge

Automatic merge is an immediate, source-bound exception for ordinary
documentation in PR-style repositories. It is authorized only when all of the
following are true at decision time:

1. The trusted base contains valid current configuration with
   `features.tiered_review: true`, `workflow_style: pr`, and the secret guard
   enabled. Missing, malformed, disabled, or revoked configuration fails
   closed.
2. Every changed entry is ordinary prose documentation. Classification checks
   both old and new names for renames and checks file modes. Code,
   dependencies, legal or governance material, process or security policy,
   agent/editor/plugin controls, workflows, configuration, skills, harnesses,
   executable or non-regular files, and uncertain paths require human review.
3. The target branch has an active strict ruleset with no applicable bypass for
   the automation actor. Every required check is matched to its exact expected
   source and has a successful latest attempt for the current head SHA.
   Configured-but-missing applicable CodeQL fails closed.
4. Immediately before mutation, the worker rechecks pull request identity,
   open state, base, current head SHA, eligibility, ruleset, and checks. It then
   calls the REST merge endpoint with the current head SHA and no prior
   persistent authorization.

The worker never enables GitHub `auto_merge`, carries no reusable approval,
and provides no automatic break-glass path. Unknown pre-existing `auto_merge`
state is reported with a manual migration action; setup and health checks do
not silently disable it.

A successful configured check proves only that the named check completed for
the bound source and commit. It does not prove semantic safety. The REST head
condition prevents a changed head from merging, while the strict ruleset must
enforce base freshness and required checks at merge time because REST cannot
atomically bind the earlier base observation.

### Repository protection and release

Setup is additive and never-clobber:

- PR/tiered mode may provision strict, exact-source required-status rules.
- Ordinary trunk may add only compatible deletion and non-fast-forward
  safeguards. It preserves every stricter existing control and reports
  pre-landing status enforcement as unconfigured unless the user explicitly
  selects a PR or staging mechanism.
- Missing API access, unknown settings, malformed responses, absent applicable
  checks, and partial health data remain unknown or fail closed as appropriate;
  they are never translated into healthy.

Release authorization binds the exact candidate commit to default-branch
ancestry and to the successful latest attempts of every named applicable
workflow. A green branch, a successful older attempt, or an unrelated run is
insufficient.

### Control-path review

The secret guard and review briefings use a conservative shared concept of
automation and policy controls. It includes nested `AGENTS.md`, `CLAUDE.md`,
and `SKILL.md`; native `.agents/` and `.codex/` controls; Claude/Codex plugin
metadata; GitHub agent and workflow controls; `.sdlc/`, `docs/agents/`, and
`docs/sdlc/` policy; harness documents; and relevant editor automation.
Renames are surfaced by both names and mode-only changes are surfaced.

Those paths warn and require reviewer explanation. Only recognized
agent/editor settings JSON is content-blocked for supported executable command,
hook, task, terminal, and encoded-value patterns. Ordinary `.sdlc` state and
configuration or plugin-manifest hashes remain warning-only unless another
secret or credential rule matches. Generic Markdown prose is not blocked
merely because it contains a command. The scanner is heuristic: it may warn on
legitimate changes and miss unsafe semantics, so a clean result is not a safety
guarantee and does not replace human review of control changes.

## Consequences

- This decision supersedes ADR 0008's dependency lane, persistent auto-merge,
  and automatic break-glass contract. ADR 0004's human-merge lane remains the
  default and applies to every non-qualifying or uncertain change.
- The expanded control-path contract supersedes the narrower coverage
  assumption in ADR 0005 while preserving its three layers and false-positive
  review path.
- Scheduled collection does not prove a review loop completed. Unavailable
  alert APIs or skipped agent assignment are reported as incomplete/unknown,
  consistent with ADR 0006's health purpose.
- Never-clobber applies to local files and additive remote setup: unknown state
  is surfaced for a human rather than overwritten into a guessed default.
- This contract bounds authorization and refusal behavior. It does not prove
  productivity gains, defect reduction, complete secret detection, or safety
  across every repository, provider, or plan.
