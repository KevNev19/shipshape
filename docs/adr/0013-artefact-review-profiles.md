# 0013 — Artefact review profiles

Date: 2026-10-14

## Status

Accepted

## Context

[ADR 0007](0007-findings-first-review.md) gave every review one finding
contract, and its evidence and rubric are written for code: a check result
or a file and line, behaviour, blast radius. Many changes are not code: a
specification, an implementation plan, a decision record, a change-intent
file from [ADR 0009](0009-lightweight-change-intent.md), a README. Read with
code questions, a specification's contradictions and untestable
requirements, a plan's out-of-order or unverified steps, and a document's
stale statements go unexamined. Tools that run reviews for a repository
also have to choose what to ask from the changed files alone, which prose
in a skill cannot give them.

## Decision

1. Every review uses exactly one of four profiles, listed in this order:
   specification, plan, documentation, code. The order decides which
   profile a changed file fits and breaks ties.
2. `skills/shipshape-review/references/profiles.json` is the
   machine-readable source: `version` 1 and, per profile, `name`, `paths`
   (glob patterns: `*` within one folder, `**` across folders, neither
   matching a name that starts with a dot) and `lenses` (`key` and
   `prompt`, most important first). Every profile has a `security` lens
   among its first three. `code` is listed last and takes every path no
   earlier profile matches.
3. A changed file fits the first profile, in that order, whose patterns
   match its path, and fits code when none does. A change is reviewed under
   the profile that fits the most changed files when that is at least half
   of them, the earlier profile on a tie, and as code otherwise. A changed
   file that fits another profile is still reviewed for what that profile
   looks for; its findings join the same report.
4. The finding contract gains section 0: the profiles, how a file fits one,
   how one is chosen, and what a finding's evidence points at under each.
   The Intent part names the profile and how many of the changed files fit
   it. The five report parts, the verdict strings and the two automatic
   escalations do not change, and security is checked under every profile.
5. As ADR 0007 requires, the three review surfaces change together in one
   release. The generated GitHub briefings carry the profiles in words,
   because `profiles.json` is not rendered into a consumer's repository.
   `tests/test_review_profiles.py` pins the shared rules across the three
   surfaces, the fitting rule in the contract, and the profile names and
   order across the contract and `profiles.json`.

## Consequences

- This extends [ADR 0007](0007-findings-first-review.md) and does not
  supersede it: `tests/test_review_contract.py` is unchanged and passes.
- A profile changes the questions a review asks, never which changes are
  security findings. The control-path review of
  [ADR 0005](0005-agent-control-files-security-sensitive.md), as widened by
  [ADR 0010](0010-source-bound-automation-and-control-policy.md), applies
  under every profile, and the generated reviewer keeps its two control-file
  sentences verbatim: `doctor.AGENT_CONTROL_REVIEW_MARKERS` looks for them
  in the reviewer briefing, and the agent control-file coverage check FAILs
  without them, so a later edit to the template must keep both unbroken.
- Files under dot-named folders such as `.github/` and `.claude/` match no
  pattern and fit code, so they get the code profile's security lens.
  `AGENTS.md`, `CLAUDE.md`, `SKILL.md` and the documents under
  `docs/agents/` and `docs/sdlc/` fit documentation, whose security lens
  asks what such a file now lets an agent do.
- Consumers receive the new briefing text on their next apply; a briefing
  they have edited is a drift conflict and is never overwritten
  ([ADR 0003](0003-token-substitution-templates.md)).
- `profiles.json` changes its `version` only when its shape changes; new
  patterns or lenses keep version 1.
- Rejection criterion: if profiled reviews of mixed changes miss findings
  a code review of the same change would have caught, a change that touches
  any code file goes back to the code profile, rather than profiles being
  withdrawn.
