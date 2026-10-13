# Shipshape assurance evaluation

Status: locally and live accepted on 2026-10-13, except one item: publishing a
release with the corrected release helper (see Releases below).

This evaluation checks whether Shipshape's setup, guard, review, release and
health behavior matches its promises. It combines implementation inspection,
adversarial tests, independent review and trials in the two existing disposable
repositories. The starting kit commit was
`e8e34e96cda1f60eb4904fc5fe4eb4974f736ff6`; kit changes remain uncommitted on
`main` until the user commits them. No kit release is being published by this
evaluation. The run stopped on 2026-09-10 when the Codex worker hit its usage
limit, and resumed on 2026-10-13; see the final section.

## Acceptance criteria

| Area | Required observable behavior | Current assessment |
| --- | --- | --- |
| Setup and repair | Preview does not mutate the consumer; apply detects a changed proposal; user bytes, modes, configuration and design edits survive repair; versions and partial state are truthful. | Integrated local gates and actual Claude CLI fresh preview, apply and repair pass. On 2026-10-13, a re-render of both runtime proposals proposed only the expected release-template update and kept the trunk `CLAUDE.md` edit as a conflict. |
| Dependency installation | Supported package managers use matching lockfiles and a working, reproducible installation sequence. | Fresh-input restrictions pass focused tests; all 30 final hosted manager jobs passed real behavioral tests across Node 24, 25 and 26. |
| Secret and control checks | Introduced commit history is scanned with trusted policy; inspection failures stop the check; foreign hooks survive; documented control patterns are surfaced without blocking ordinary state hashes. | Integrated local checks, live history rejection, and actual execution of the CLI-installed hook pass. |
| Automatic merging | Explicit trusted opt-in, narrow ordinary-document paths, exact current-head evidence, strict source-bound protection and an immediate SHA-conditioned merge are required. | Live on 2026-10-13: a README-only PR merged at its verified head after all checks passed, under the Shipshape ruleset. A code PR and an agent-settings PR were refused on every wakeup and remain open. |
| Releases | The exact candidate and immutable tag have valid ancestry, current required workflow evidence and an active publisher; publication is verified afterward. | A live release succeeded with the earlier helper. Independent review then found the CodeQL findings gate could never pass on push commits; it was corrected to use code-scanning analyses and alerts. The corrected gate passed live on a clean tip and refused a real open high alert. Publishing a release with the corrected helper has not been done yet. |
| Health and reporting | Installed configuration is distinguished from observed execution; unavailable data differs from zero findings; collection and assignment are not called completed review. | Both integrated doctors agree in the CLI trial. The corrected snapshot passed hosted Python 3.10 and 3.14 and hosted CodeQL on 2026-10-13. |

## Evidence already observed

- The initial local suite had **177 passing tests and one date-dependent
  failure**. After integration, the coordinator independently observed
  **591 passing tests**, **27/27 dated regression checks**, Ruff lint and
  formatting, and mechanical e2e passing. The 183 non-research source files
  were unchanged across that run. Later hosted failures remain open below;
  local green is not a substitute for hosted acceptance.
- Claude CLI loaded the local plugin and invoked `shipshape:shipshape-init`.
  Its saved preview left all original consumer files unchanged. Approved apply
  reported an exact digest match, wrote the setup, installed the local hook,
  and ran the consumer's real arithmetic test. Both doctors independently
  reported 12 PASS and one FAIL for deliberately unavailable remote protection.
  The actual installed pre-commit dispatcher blocked a synthetic key with
  `secret-guard` exit 1. No fixture commit was made. This is a scripted
  functional trial, not a human usability study.
- Local frozen installs and meaningful arithmetic tests passed for
  npm 10.8.2, pnpm 10.15.1, Yarn 1.22.22, Yarn 4.9.2 and Bun 1.2.20.
  The actual rendered CI and Copilot setup jobs also passed on Node 24/Ubuntu:
  [all ten hosted jobs](https://github.com/KevNev19/shipshape-e2e-trunk/actions/runs/34412444097).
  Those initial hosted jobs proved installation only: their test steps used
  placeholders. The meaningful arithmetic checks were local. A new isolated
  trial rendered explicit behavioral test commands across Node 24, 25 and 26:
  [all 30 jobs passed](https://github.com/KevNev19/shipshape-e2e-trunk/actions/runs/34417872927).
  The coordinator checked each job's actual command, one passing workspace
  behavior test, zero failures, and matching source hashes. Neither trial is a
  Copilot coding session.
- A proposed change introduced a synthetic secret, removed it from the final
  tree, and replaced the proposed scanner with an always-successful script.
  The trusted-base scan still rejected the introduced history:
  [negative PR](https://github.com/KevNev19/shipshape-e2e-trunk/pull/3),
  [expected failed scan](https://github.com/KevNev19/shipshape-e2e-trunk/actions/runs/34413295474).
- The first disposable release exposed a missing explicit repository argument
  when publishing without a checkout. Its immutable tag was retained. After
  correction, publication and exact-tag postflight succeeded for
  `a76c39b71f7e516ccf0c6f92e0732c2ccdc756ce`:
  [successful workflow](https://github.com/KevNev19/shipshape-e2e-trunk/actions/runs/34414774851),
  [trial release](https://github.com/KevNev19/shipshape-e2e-trunk/releases/tag/v0.0.0-assurance-20260909.2).
- A live read verified the newly added trunk ruleset contains only deletion and
  non-fast-forward safeguards, with no bypass actors. Ordinary-push verification
  remains to be completed with the final trial update.

## Independent review and remaining corrections

The first fresh implementation review produced eight actionable findings:

1. Bind apply to the reviewed candidate and rendered plan.
2. Detect raw-byte and mode changes before replacement or removal.
3. Keep installed, rendered and completed upgrade versions consistent.
4. Reject unsupported mutable dependency or manager resolution on new setup.
5. Handle the absence of bundled Corepack in Node 25 and later.
6. Include a later rerun of an older workflow in release evidence selection.
7. Require an active publication workflow before approving a tag push.
8. Use the same exact cutoff for verification minutes and merged changes.

Additional coordinator probes found common plural policy directories could
still qualify for automatic merging, and the new report collector retained a
synthetic secret field in JSON and treated a full first PR page as complete.
Only synthetic alert data was used for the secret-output probe. Independent
reruns now confirm that the secret marker and unknown fields are absent from
both JSON and issue text, page two is read for 51 PRs, and the three plural
policy-directory cases are rejected while an ordinary usage guide is accepted.

The live bootstrap PR remains unmerged while final integration is prepared.
Its CodeQL diagnostic was traced to name-based classification of a function
returning fixed guard-status messages. A two-line function/call rename cleared
the hosted CodeQL check and marked the alert instance fixed, without dismissal
or suppression. Separate tests verify that arbitrary credential-like config
and hook contents are not echoed.
([CodeQL run](https://github.com/KevNev19/shipshape-e2e-pr/actions/runs/34419326001),
[test PR](https://github.com/KevNev19/shipshape-e2e-pr/pull/7))

Automatic approval review rejected a direct update to the disposable trunk
repository's default branch. The final Node trial instead runs on an isolated
fixture branch. Default-branch integration and ordinary-push validation require
separate approval; an isolated branch trial does not establish those results.

A second independent review found confirmed gaps in policy-path eligibility,
partial GraphQL errors, multiline executable settings, requested protection
inspection, machine-readable report truncation, and an access command summary.
The coordinator independently observed **279 focused tests passing** against
stable guard, report, review and protection source hashes. Repeated probes now
reject split executable settings, partial GraphQL state, and the three policy
document examples while accepting the ordinary usage guide. Doctor caller
integration subsequently passed the full local gates. Self-host regeneration
wrote nine managed artifacts while preserving all six custom-file conflicts;
the renderer accurately retained partial status.

Its principal GitHub SHA finding was contradicted by live observations: the
captured CI, CodeQL and `pull_request_target` scanner REST runs, jobs and checks
all identify the PR head SHA and use bare workflow paths. Runtime `GITHUB_SHA`
event semantics are distinct from the REST `head_sha` field. Exact-head binding
is retained; captured response shapes are covered by regression fixtures. This
does not establish that every unobserved API variant is supported.

The first final hosted Python 3.10 run reached the suite and reported
566 passed and 25 failed: 24 local-hook tests inherited GitHub's execution
environment, and the isolated source snapshot omitted one workflow used by a
test. The test harness and snapshot are being corrected without changing the
production doctor's CI behavior or skipping cases.
([compatibility run](https://github.com/KevNev19/shipshape-e2e-trunk/actions/runs/34420533244))

Final hosted CodeQL also raised three diagnostics involving fixed release
workflow metadata, a synthetic report fixture, and Git blob SHA-1 identity in
a test. Their full traces are retained; no scanner suppression or alert
dismissal has been applied. Final review, the rest of the CLI repair trial,
and reruns of the corrected hosted candidate remain pending.

## Research conclusions

The research supports testing the mechanisms above; it does not establish
Shipshape's effect on productivity or production defects. The existing research
documents now distinguish the original METR experiment from its later follow-up,
survey association from causation, and structural assertion detection from
behavioral test quality.

METR's February update qualifies a separate follow-up, rather than retracting
its original early-2025 slowdown result. Its May survey adds self-reported,
selection-limited context, not a measured Shipshape effect.
([February update](https://metr.org/blog/2026-02-24-uplift-update/),
[May survey](https://metr.org/blog/2026-05-11-ai-usage-survey/))

DORA associates greater adoption with both throughput and instability;
Cloudflare's reported review-approval override rate has a different denominator
from Shipshape's automatic eligibility. Neither supplies a deployment threshold
for this system.
([DORA](https://dora.dev/insights/balancing-ai-tensions/),
[Cloudflare](https://blog.cloudflare.com/ai-code-review/))

The supported automation policy is recorded in
[ADR 0010](../adr/0010-source-bound-automation-and-control-policy.md).
Passing configured checks establishes bounded evidence about those checks;
it does not prove semantic safety, complete secret detection, universal
repository compatibility or long-term delivery improvement.

## Evidence custody

Raw prompts, execution streams, unchanged worker handoffs, failures, reruns,
source hashes and live-trial observations are retained locally under
`.codex-orchestrator/runs/2026-09-09-assurance/`. That ignored directory is not
part of the distributable plugin. Usage-limit and permission-transition
interruptions are recorded as failed executions; missing handoffs were not
invented. Final portable evidence and accepted source hashes will be added
after the remaining corrections and trials.

## Resumed completion (2026-10-13)

The run was resumed in the same journal, not in a new run. Its results:

- **Interrupted task.** The worker stopped mid-task on the CodeQL findings
  gate and left no handoff, so the run records it as a failed execution. The
  code and tests it left behind were checked independently.
- **Generated copies.** The kit's own rendered release helper and workflow had
  fallen behind their templates. They were regenerated through the normal
  plan/apply path.
- **Local gates.** 621 tests, Ruff lint and formatting, 30/30 dated
  regressions and mechanical e2e passed.
- **Hosted compatibility.** The current snapshot ran in isolated PR 4 at
  `e6724dc`, which verifies 137 source hashes. The full suite passed on Python
  3.10 and 3.14
  ([run](https://github.com/KevNev19/shipshape-e2e-trunk/actions/runs/38319007357)).
- **Hosted CodeQL.** The CodeQL findings checks passed with no new alerts on
  trunk PR 4 and PR 5 and on PR-style PR 7.
- **Automatic merge.** After the user merged PR 7, the Shipshape-owned ruleset
  was applied
  ([merged README-only PR](https://github.com/KevNev19/shipshape-e2e-pr/pull/8);
  [refused code PR](https://github.com/KevNev19/shipshape-e2e-pr/pull/2);
  [refused agent-settings PR](https://github.com/KevNev19/shipshape-e2e-pr/pull/4)).
- **Release CodeQL gate.** The September independent Claude CLI review had
  finished but was never recorded. Its high-severity finding still held: GitHub
  creates no CodeQL findings check run on default-branch push commits, so every
  CodeQL-enabled release was refused. The gate now requires an exact clean
  CodeQL code-scanning analysis for the candidate, and it refuses open high,
  critical or error-level CodeQL alerts. Missing, stale, ambiguous, malformed
  or unauthorized evidence also stops the release.
- **Default-tip limit.** GitHub reports only each alert's latest branch
  instance, not a historical snapshot for an older commit. When CodeQL is
  enabled, the candidate must therefore be the current default-branch tip.
- **Release workflow permissions.** The workflow gains `security-events: read`.
- **Live test of the corrected gate.** It passed the kit repository's clean tip
  `5cc6966` using its exact analysis. It refused `shipshape-e2e-trunk`'s tip
  with that repository's real open high alert #1.

Remaining limits:

- No release has been published with the corrected helper.
- The merge made by the automatic-merge bot did not trigger push workflows on
  the PR-style repository. That is the GitHub limitation the release checklist
  already describes.
