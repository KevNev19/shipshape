# shipshape against the AI-native SDLC: a gap analysis

- Status: Research analysis (2026-08-13; evidence and settled-policy alignment
  corrected 2026-09-09)
- Purpose: compare the kit shipshape v0.2.1 actually delivers with the
  verification-centric lifecycle developed in
  [0001 — Challenging the traditional SDLC](0001-ai-native-sdlc.md), and turn
  the differences into bounded design options.
- Policy relationship: kit policy remains in
  [docs/agents/harness.md](../agents/harness.md). This analysis changes no
  policy. Any conclusion that changes a settled decision would require a new
  ADR that supersedes the existing one.

---

## Method

The conclusions in 0001 were extracted and sorted by evidence strength, while
the kit's templates, skills, scripts, and policy were independently inventoried
and classified in Böckeler's guides/sensors × computational/inferential frame.
Every gap below joins one tiered research finding to one verified fact about the
kit; where the evidence does not support a change, the register says so rather
than turning direction-of-travel into doctrine.

The unamended "Current state," proposal, and classification paragraphs below
are the dated 2026-08-13 snapshot, not assertions about the checkout on
2026-09-09. Gaps 1, 3, 5, and 6 carry explicit later evidence. The historical
roadmap at the end records sequencing rationale rather than completed work.

## What the research validates

"Automation proposes, CI checks, a human merges" remains the right small-team
default for now, and is implemented by [ADR 0004](../adr/0004-github-agents-support.md)
and the generated [`AGENTS.md`](../../templates/adapters/AGENTS.md.tmpl).

Frozen fixtures remain ground truth through `tests/expected/*.json` and the
non-regeneration rule in [`docs/agents/harness.md`](../agents/harness.md).

Red CI remains a stop sign in every generated CI variant under
`templates/github/workflows/ci-*.yml.tmpl` and in
[`templates/harness/sdlc-harness.md.tmpl`](../../templates/harness/sdlc-harness.md.tmpl).

Every fixed bug continues to leave a dated regression in
[`tests/regressions.py`](../../tests/regressions.py), as required by
[`docs/agents/harness.md`](../agents/harness.md).

Security remains default-on through
[`templates/hooks/secret-guard.sh.tmpl`](../../templates/hooks/secret-guard.sh.tmpl)
and the consequence gate in
[`skills/shipshape-customize/SKILL.md`](../../skills/shipshape-customize/SKILL.md).

The model-neutral harness with thin host adapters remains sound through
[`templates/harness/sdlc-harness.md.tmpl`](../../templates/harness/sdlc-harness.md.tmpl),
[`templates/adapters/CLAUDE.md.tmpl`](../../templates/adapters/CLAUDE.md.tmpl),
and [`templates/adapters/AGENTS.md.tmpl`](../../templates/adapters/AGENTS.md.tmpl).

## Gap register

### 1. Test quality is not sensed

**Gap.** The verification-centric lifecycle asks whether tests can detect a
wrong implementation, not merely whether they execute lines. Shipshape has no
integrated mutation score, coverage gate, or general test-quality sensor; its
kit-local assertion scan is only a structural advisory.

**Evidence.** The four-repository study in
[0003](0003-test-quality-precision-study.md) is a small observational precision
sample of one structural Python heuristic. It measured neither recall nor
mutation sensitivity. At repository root, both `assert True` and an assertion
inside an uncalled nested function pass unflagged, demonstrating that assertion
presence is not evidence that a test can detect wrong behavior. Coverage and
property-based-testing literature remains design context, not product efficacy.

**Current state.** `scripts/test_quality.py` is a kit-local prototype. It is
not rendered into consumer repositories, wired into CI, or treated as a gate.
Its output identifies tests with no recognized assertion syntax; it does not
score test quality.

**Bounded next step.** Keep the prototype advisory and kit-local. A mutation
experiment may compare flags with killed mutants and measure runtime; a larger,
predeclared corpus may estimate recall as well as precision. Until then, do not
add a `test_quality` feature, consumer workflow, doctor status, or merge gate.

**Classification — `research-first`.** The prototype supports only a warning
about recognizable assertion absence. Cross-language behavior, recall,
mutation sensitivity, and CI cost remain unmeasured.

**Constraint check.** The prototype is Python stdlib and JSON-only under ADR
0002. It remains kit-local, creates no consumer workflow or doctor state, and
does not alter the ADR 0003 or ADR 0004 contracts.

### 2. Scheduled health exists, but unknown is not healthy

**Original gap.** The lifecycle called for stewardship outside the change path,
but shipshape's drift and setup sensor was invoke-only.

**Evidence.** The named §6 gap is supported by the harness-engineering model:
continuous drift monitoring closes the feed-forward-only failure mode. This is
a Tier 2 design pressure, reinforced by the explicit keeper/gap judgment in
0001; it is not inferred from user perception.

**2026-09-09 state.** [ADR 0006](../adr/0006-scheduled-consumer-stewardship.md)
settled this gap. The manifest now renders a self-contained doctor and weekly
workflow behind default-on `scheduled_health`, with never-clobber handling.
The remaining boundary is evidence quality: missing API access, unavailable
sections, or a skipped handoff must stay WARN/unknown rather than being counted
as a healthy or completed loop.

**Classification — `settled with an evidence boundary`.** ADR 0010 reinforces
the unknown-state rule; the production inferential-loop limitation is recorded
in gap 3.

**Constraint check.** The rendered doctor is stdlib-only and JSON-only under
ADR 0002; both artifacts are token-only, manifest-selected, and
ask-if-drifted under ADR 0003; the job reports findings and never merges under
ADR 0004; and its issue uses plain PASS/WARN/FAIL language with one next action.

### 3. The weekly inferential security-quality sensor is kit-local

**Gap.** Shipshape has built an inferential stewardship loop for itself, but
does not ship it. Consumers therefore receive no inferential sensor that fires
automatically.

**Evidence.** Tier 2 evidence says AI failures skew toward deeper design and
security faults, while the v0 model places expensive inferential sensors after
deterministic checks. It also warns that a broken judge is worse than no judge,
and §7 explicitly leaves open whether v0.3 should ship any inferential sensor.
That qualification prevents an immediate rollout.

**Current state.** [`.github/workflows/security-quality-report.yml`](../../.github/workflows/security-quality-report.yml)
gathers CodeQL, Dependabot, secret-scanning, CI, permissions, and pull-request
data each week, then opens an issue. [`.github/agents/security-quality.md`](../../.github/agents/security-quality.md)
turns it into one dated report-only pull request. Both are explicitly
kit-local and absent from [`templates/manifest.json`](../../templates/manifest.json);
automatic assignment also depends on an `ACTIONS_PAT` user secret.

The 2026-09-09 production observation is incomplete: issue 11 contains raw
collected data, alert APIs were unavailable, and agent assignment was skipped.
Unavailable alert sections are unknown, not empty, and a raw issue is not an
inferential review. This is evidence of collection plus a broken handoff, not a
completed weekly loop.

**Proposed change, concretely.** Treat the existing pair as a prototype, not a
template ready to copy. After evaluation, create
`templates/github/workflows/security-quality-report.yml.tmpl` and
`templates/github/agents/security-quality.md.tmpl`, rendered to their current
destinations with pillar `security`, overwrite policy `ask-if-drifted`, feature
flag `security_quality_report` defaulting off during evaluation, and no
additional `when` condition. The
workflow shape remains weekly plus manual dispatch: a deterministic gather job
with read-only code/security access and issue write, followed by agent
assignment only when the token is present. Without the token it must say that
the inferential step did not run; a raw-data issue is not an inferential
report. Add a doctor check named `weekly security-quality report`: PASS when
the workflow, agent briefing, and named secret are visible through `gh`; WARN
when secret visibility or agent assignment cannot be verified; FAIL when the
feature is enabled but either managed file is missing. Its next action would
be: "Add the ACTIONS_PAT repository secret, or turn this report off after
reading what will no longer be checked."

**Classification — `research-first`.** Shipping is unlocked by a small eval
set measuring omitted alerts, invented findings, severity calibration, report
cost, and whether assignment can be made reliable without surprising token
scope. Until then, the research's calibrated-judge warning controls.

**Constraint check.** Deterministic helpers remain stdlib/JSON under ADR 0002;
the workflow and briefing are token-only, condition-selected, and
ask-if-drifted under ADR 0003; the agent opens a report PR and never changes or
dismisses security controls under ADR 0004; and the briefing preserves the
plain-language, consequence-first voice.

### 4. Review still presents a diff summary rather than verified findings

**Gap.** Shipshape's review surfaces are disciplined, but their organizing
unit is still the change: read the whole diff, summarize behavior and risk,
then give a verdict. The research asks the human to receive verified findings
and an intent-conformance account instead.

**Evidence.** Tier 1 evidence from the 8.1-million-PR LinearB dataset places
the failure in reviewer pickup queues, while Finster's Tier 1 sampling-rate
argument says review degrades around large diffs and that adding blocking
reviewers does not repair the mismatch. The research's conclusion is to
present findings, not diffs; that conclusion does not depend on the contested
rubber-stamping literature.

**Current state.** [`skills/shipshape-review/SKILL.md`](../../skills/shipshape-review/SKILL.md)
requires the full diff and emits "What this change does," checks, risks,
security notes, and a verdict. The same four-step rubric is condensed into
[`templates/github/agents/reviewer.md.tmpl`](../../templates/github/agents/reviewer.md.tmpl)
and [`templates/github/copilot-instructions.md.tmpl`](../../templates/github/copilot-instructions.md.tmpl).

**Proposed change, concretely.** Add
`skills/shipshape-review/references/finding-contract.md` and make all three
surfaces report: intent available or missing; verified findings ordered by
severity; intent conformance; material uncertainties; then the existing exact
verdict. Each finding would carry a check or file/line as evidence, the
plain-language consequence, and one next action. "No verified findings" must
not mean "no risk": green required checks, missing intent, and inspection
limits remain visible. The skill still reads the whole diff internally, but
does not narrate it file by file. The generated reviewer remains an
ask-if-drifted `process` template under the existing `github_agents` flag; no
new manifest condition is needed.

**Classification — `needs-ADR`.** This changes the settled review contract
shared by the plugin skill and ADR 0004's generated reviewer, even though it
does not remove the human merge gate.

**Constraint check.** No new runtime violates ADR 0002; the generated
briefings stay token-only and never-clobber under ADR 0003; findings still end
in a human merge decision under ADR 0004; and each finding follows the kit's
short, evidence-linked, consequence-first voice.

### 5. Automation and policy controls need conservative path coverage

**Gap.** The original scope covered root `AGENTS.md` and `CLAUDE.md` plus a
small set of `.claude/` and `.vscode/` paths. It missed nested instructions,
native `.agents/` and `.codex/` controls, skills and plugin manifests, workflow
and editor automation, and harness/SDLC policy at other depths.

**Evidence.** Tier 1 evidence from the keyv compromise shows valid provenance
on malware whose payload used `.claude/` and `.vscode/` files that scanners did
not read. The supported conclusion is narrow: provenance is not intent, and
agent/editor configuration needs explicit inspection. It does not support the
claim that every such file is malicious.

**Current state.** The guard now preserves the file, content, history,
binary-data, rename, and inspection-error protections already present while
applying one control-path classifier in staged and range modes. Both sides of a
rename and mode-only changes are inspected.

**Corrected contract.** Changes to those control paths produce a warning and a
reviewer escalation. Supported agent/editor settings JSON still blocks known
executable command, hook, task, terminal, or encoded-value patterns. Ordinary
`.sdlc` state/configuration and plugin-manifest hashes are warning-only unless
an independent secret or credential rule matches. Markdown outside a named
control path remains non-blocking. The classifier is conservative and
heuristic: warnings can be false positives, content patterns can miss risky
settings, and passing the guard cannot guarantee safety. Legitimate control
edits remain possible after review; this is not a blanket ban.

**Classification — `settled correction`.** [ADR 0010](../adr/0010-source-bound-automation-and-control-policy.md)
supersedes the narrower path assumptions without weakening existing security.

**Constraint check.** The existing native shell guard remains ADR 0002's
allowed hook form and adds no dependency; template changes remain token-only
and ask-if-drifted under ADR 0003; agent-surface changes are findings for the
human merger under ADR 0004; and WARN/FAIL output explains the consequence and
one next action without blame.

### 6. Review authority needed a bounded exception

**Gap.** Every agent-authored change ends at the same human merge gate,
regardless of whether it is a docs-only correction or a security-sensitive
workflow change. The research proposes authority proportional to risk.

**Evidence.** Queue and sampling evidence motivates examining the human gate;
it does not prove that automatic merge improves Shipshape outcomes. Cloudflare
reported a 0.6% rate for humans overriding its AI reviewer approval, a different
system and denominator from Shipshape path eligibility. It is context only,
not a local threshold
([Cloudflare](https://blog.cloudflare.com/ai-code-review/)).

**Current state.** [ADR 0008](../adr/0008-tiered-review-authority.md) settled a
docs/dependency lane using persistent auto-merge and a break-glass concept.
Implementation review found those bounds too broad and the authorization too
persistent. [ADR 0010](../adr/0010-source-bound-automation-and-control-policy.md)
supersedes that contract.

**Corrected contract.** Only ordinary documentation can qualify. Code,
dependencies, legal/governance/process/security material, agent/editor/plugin
controls, workflows, configuration, skills, harnesses, and uncertain paths are
human-reviewed. Classification checks old and new rename paths plus file modes.
Eligibility requires the trusted base to contain explicit current
`tiered_review: true`, `workflow_style: pr`, and enabled guard configuration.
Missing, malformed, or revoked configuration fails closed. Every exact
source-bound required check must be successful for the current head under a
strict active ruleset; configured-but-missing applicable CodeQL also fails
closed. Green configured checks show only that those checks passed, not that a
change is safe.

The worker performs an immediate SHA-conditional REST merge. It never grants
persistent auto-merge authorization and has no automatic break-glass path.
GitHub's REST merge can bind the head SHA but cannot atomically freeze the base
branch observed during classification, so strict server-side enforcement is a
required second boundary. Unknown pre-existing `auto_merge` state is surfaced
for manual migration and is never silently disabled.

**Classification — `settled correction`.** ADR 0010 is the authority. It
removes the dependency lane and persistent authorization from ADR 0008.

**Constraint check.** Setup remains additive and never-clobber. Ordinary trunk
may add compatible deletion and non-fast-forward safeguards while preserving
stricter existing controls, but it cannot add pre-landing required statuses
when the direct push is what starts CI. PR/tiered mode may provision strict
exact-source status enforcement. Health reports missing or unverifiable remote
state as unknown, never healthy by assumption. Release binds the exact tested
default-branch ancestry and named latest runs rather than a merely green branch.

### 7. Per-change intent is partial and not durable in the repository

**Gap.** Shipshape asks what a PR does and why a task matters, but it does not
leave a lightweight, versioned statement of problem, constraints, non-goals,
and acceptance criteria for the implementation and reviewer to share.

**Evidence.** Tier 2 evidence supports intent capture and the
verification-to-validation shift: agents can check conformance more cheaply
than humans can decide whether the target was right. Tier 3 SDD evidence and
the Scott Logic n=1 result warn that elaborate spec pipelines can create large
ceremony without fewer bugs. The Tier 2 pressure drives the gap; the Tier 3
warning constrains the shape and cannot justify a heavier process.

**Current state.** [`templates/github/PULL_REQUEST_TEMPLATE.md.tmpl`](../../templates/github/PULL_REQUEST_TEMPLATE.md.tmpl)
asks what changed, how it was checked, and what is risky.
[`templates/github/ISSUE_TEMPLATE/task.yml.tmpl`](../../templates/github/ISSUE_TEMPLATE/task.yml.tmpl)
asks what and why. [`templates/docs/design-doc.md.tmpl`](../../templates/docs/design-doc.md.tmpl)
is durable but project-level and write-once. None is a per-change in-repo
acceptance artifact.

**Proposed change, concretely.** Add a short managed source template at
`templates/docs/change-intent.md.tmpl`, rendered to
`.sdlc/templates/change-intent.md` with pillar `process`, overwrite policy
`ask-if-drifted`, and no condition or feature flag. Add a
`scripts/intent.py create <repo> --slug <slug> --input <json-file>` helper that
validates four short fields — problem, constraints, non-goals, acceptance
checks — refuses an existing destination, and emits
`{"ok": true, "action": "created", "path": "docs/changes/YYYY-MM-DD-<slug>.md", "next_action": "..."}`.
A new `skills/shipshape-intent/SKILL.md` would conduct the short interview,
recommend no artifact for a trivial typo-only change, show the proposed file,
and invoke the helper only after confirmation; the skill owns sequencing and
translation, not file-generation logic. The generated intent file is
user-owned and never silently revised after acceptance. The PR and task
templates would link to it when one exists rather than duplicate it. Review
gap 4 can then report conformance or state plainly that no intent artifact was
warranted.

**Classification — `needs-ADR`.** Requiring or recommending a durable
per-change artifact changes the consumer process contract. The ADR must define
the trivial-change escape hatch and when the artifact may be updated after
implementation begins.

**Constraint check.** The helper is Python stdlib with one JSON stdout object,
and the skill only sequences it under ADR 0002; the source is token-only and
ask-if-drifted while each created intent file is explicitly user-owned under
ADR 0003; agents still propose and humans still merge under ADR 0004; and four
short questions preserve the non-engineer voice and anti-ceremony constraint.

### 8. Flaky-test retries can be introduced without a health warning

**Gap.** Shipshape's own CI does not retry failed tests, which is good, but no
sensor tells a consumer when a later workflow starts hiding failures behind a
retry loop or retry action.

**Evidence.** Tier 2 evidence characterizes flaky-test retries under high
change arrival as a self-inflicted denial of service: they multiply queue and
compute load while weakening the meaning of green. This is consistent with,
and subordinate to, the Tier 1 red-CI keeper.

**Current state.** The four `templates/github/workflows/ci-*.yml.tmpl` variants
run the test command once. [`scripts/doctor.py`](../../scripts/doctor.py) checks
that CI exists and that workflows declare permissions, but not whether CI
retries failures.

**Proposed change, concretely.** Add a doctor check named `test retries` using
a deliberately narrow text scan over `.github/workflows/*.yml`: PASS when no
known retry action or shell retry-loop marker appears around the configured
test command; WARN when a marker is found or the pattern is ambiguous; never
FAIL on text inspection alone. The next action would be: "Remove the retry and
fix or quarantine the flaky test so one green run means the test passed."
Document the check's naive boundary beside the existing workflow-permissions
audit. No CI template or manifest entry needs to change.

**Classification — `do-now`.** This adds a read-only warning that reinforces
existing red-is-a-stop-sign behavior and makes no new merge or platform
commitment.

**Constraint check.** The check uses Python stdlib and remains inside the
doctor's single JSON object under ADR 0002; it writes no template and cannot
clobber under ADR 0003; it advises the existing ADR 0004 lane rather than
changing it; and WARN includes one plain consequence and one next action.

### 9. A merge queue is not a default worth adding

**Gap.** Shipshape has no rendered merge-queue protection or queue health
sensor. At higher arrival rates, simultaneous green branches can invalidate
one another before they land.

**Evidence.** Tier 2 evidence says merge-queue math can grow nonlinearly under
agent arrival rates. The same research keeps shipshape's human merge default
because the target is small teams and non-engineers, where attention binds
before fleet-scale queue math. The orchestration model is also explicitly a
direction of travel, not validated current volume.

**Current state.** [`scripts/gh_helpers.sh`](../../scripts/gh_helpers.sh)
configures strict required checks on a branch, and
[`templates/sdlc/config.json`](../../templates/sdlc/config.json) contains a
`branch_protection` flag, but no merge-queue workflow, ruleset template, retry
policy, or queue sensor is rendered.

**Proposed change, concretely.** No merge-queue artifact should be added now.
Retain strict branch checks through `gh_helpers.sh`; if consumer telemetry later
shows merge-time invalidation, design a GitHub ruleset/merge-group path then,
rather than shipping an idle queue and platform-specific complexity to every
small repository.

**Classification — `considered-and-rejected`.** The observed scale problem is
real, but it is not shown to be shipshape consumers' problem, and a universal
queue would add cost and setup without replacing any existing risk control.

**Constraint check.** Keeping the current helper adds no ADR 0002 runtime, no
ADR 0003 template, and no exception to the ADR 0004 human lane; existing skill
translations retain the non-engineer voice.

### 10. Verification cost is invisible

**Gap.** The lifecycle treats verification as the scarce, metered activity,
but shipshape shows health status without showing how many runs or minutes were
spent to obtain it.

**Evidence.** Tier 2 evidence shows CI and inferential-review cost scaling with
PR volume rather than headcount, and provides concrete examples of cost per run
and per merged change. It establishes a pressure, not a universal budget or a
threshold at which a team should change behavior.

**Current state.** [`scripts/doctor.py`](../../scripts/doctor.py) reports eight
presence/drift checks, while [`skills/shipshape-review/SKILL.md`](../../skills/shipshape-review/SKILL.md)
reads check results. Neither records run counts, duration, retries, or cost;
[`templates/github/workflows/ci-python.yml.tmpl`](../../templates/github/workflows/ci-python.yml.tmpl)
has a single test job with no metering step.

**Proposed change, concretely.** Prototype an invoke-only
`scripts/verification_cost.py summarize <owner/repo> --days <n>` that reads
GitHub run metadata and emits
`{"ok": true, "window_days": 30, "runs": 0, "attempts": 0, "minutes": 0, "merged_changes": 0, "minutes_per_merge": null, "estimated_cost": {"status": "unknown", "currency": null, "amount": null}, "warnings": [], "next_action": "..."}`.
Unknown billing rates must remain unknown rather than guessed. A later
`/shipshape-doctor costs` view would translate trends and identify retry or
duplicate-run waste; it would not prescribe a dollar budget by default. This
is kit-invoked analysis, so no consumer workflow or manifest entry is needed
for the prototype.

**Classification — `research-first`.** Consumer pilots must establish which
provider-neutral metric changes a decision — minutes per merge, attempts per
change, or another measure — and how to obtain it without broad credentials.
Those results, plus stable API and rate-limit behavior, would unlock shipping.

**Constraint check.** The prototype uses Python stdlib, one JSON stdout object,
and no bundled client under ADR 0002; it writes no consumer template under ADR
0003; it observes rather than changes the ADR 0004 lane; and the skill reports
cost as a plain consequence with one next action.

### 11. Agent provenance is not labeled for consumers

**Gap.** Consumers receive no consistent commit or PR metadata saying that an
agent participated. That makes incident reconstruction harder, but adding a
label risks implying more assurance than the label can carry.

**Evidence.** Tier 1 keyv evidence proves provenance is not intent: a valid
attestation accompanied malware. The v0 lifecycle nevertheless lists
provenance labeling as useful context. The EU AI Act material is explicitly a
watch item and cannot drive a kit change, and no evidence in 0001 shows that a
particular label improves quality.

**Current state.** The kit repository's local
[`scripts/check_commit_msg.sh`](../../scripts/check_commit_msg.sh) requires AI
co-author attribution, but the inventory confirms that hook is not shipped.
Consumer [`templates/harness/sdlc-harness.md.tmpl`](../../templates/harness/sdlc-harness.md.tmpl)
only requires an AI assistant to explain its change and test result;
[`templates/github/PULL_REQUEST_TEMPLATE.md.tmpl`](../../templates/github/PULL_REQUEST_TEMPLATE.md.tmpl)
has no provenance field.

**Proposed change, concretely.** If research demonstrates audit value, add an
optional `provenance_labels` feature. The PR template would gain a plain
"How was this made?" field, and a new ask-if-drifted, mode-755
`templates/hooks/commit-msg-provenance.sh.tmpl` in the `process` pillar would
validate the syntax of a self-declared `Agent-Assisted-By: <tool>` trailer. It
must never infer authorship, fail an unlabeled human commit, or count the
trailer as a security or quality gate. `templates/hooks/install.sh.tmpl` would
install the hook only when the default-off feature is enabled, with no
additional `when` condition and with per-file conflict handling unchanged.

**Classification — `research-first`.** Evidence that the label materially
improves incident response or auditability, a cross-tool vocabulary, and user
research on disclosure and privacy would unlock a policy decision. Compliance
claims and security assurance would not.

**Constraint check.** The validator remains a native commit hook allowed by
ADR 0002; its feature-gated templates are token-only and never-clobber under
ADR 0003; labels are context for the existing ADR 0004 lane, not permission to
merge; and the field asks one plain question without exposing implementation
jargon.

### 12. Progressive delivery has no supported shape or evidence base

**Gap.** No shipshape template expresses a flag, canary, health check,
promotion, or rollback. The v0 lifecycle names runtime verification as a
needed layer, but the kit ends at a tagged GitHub release.

**Evidence.** The deployment-side evidence gap is total. Section 0001 §3 says
flags and rollback as a replacement for pre-merge review are asserted and
measured by nobody; input §5 explicitly forbids that use. Tier 2 slopsquatting
evidence only says some residual risk moves toward release-time and runtime
controls. It does not validate a generic progressive-delivery implementation.

**Current state.** [`templates/github/workflows/release.yml.tmpl`](../../templates/github/workflows/release.yml.tmpl)
creates a release from a verified `v*` tag. The inventory finds no flags,
canary, deployment health, or rollback artifact anywhere in `templates/`.

**Proposed change, concretely.** Do not add a generic deploy workflow. If
controlled evidence and a supported deployment target arrive, introduce a
`progressive_delivery` feature and a `deployment_platform` config field, with
one independently tested
`templates/github/workflows/deploy-<platform>.yml.tmpl` variant per platform.
Each would render to `.github/workflows/deploy.yml`, pillar `release`, overwrite
policy `ask-if-drifted`, condition `{"deployment_platform": "<platform>"}`;
the feature would default off, and `scripts/render.py` would have to recognize
`deployment_platform` as an explicit condition rather than silently treating
an unknown condition as applicable.
The job shape would be: trigger only after green CI on the default branch;
deploy a bounded canary; run an explicit health command; promote on success;
invoke a platform-specific rollback on failure; retain manual dispatch for
rollback. It would supplement, never replace, pre-merge verification.

**Classification — `research-first`.** Controlled change-failure evidence at
high volume, rollback-success and false-rollback rates, and a concrete first
deployment platform would unlock an ADR. Vendor assertion alone will not.

**Constraint check.** Any helper would remain stdlib/JSON under ADR 0002;
platform differences are separate token-only variants with never-clobber under
ADR 0003; deployment follows green CI and does not expand the ADR 0004 merge
lane; and failure output states impact and one rollback action plainly.

### 13. `features.project_board` declares behavior that does not exist

**Gap.** The configuration claims a project-board capability with no template,
manifest entry, script branch, skill behavior, or generated artifact behind
it. A policy-as-execution system should not advertise an inert switch.

**Evidence.** Tier 2 evidence shows independent convergence from policy files
toward executable policy. The implication for shipshape is modest: declared
configuration should select real behavior. This does not establish any need to
ship a project board.

**Current state.** [`templates/sdlc/config.json`](../../templates/sdlc/config.json)
defines `features.project_board: false`. [`templates/manifest.json`](../../templates/manifest.json)
has no entry using it, and [`scripts/render.py`](../../scripts/render.py) has no
code path for it.

**Proposed change, concretely.** Remove `project_board` from the default config
template and update the frozen expected configs and config-schema tests that
encode the key. Do not add a board template merely to justify the flag. Add a
doctor check named `unused settings`: PASS when no known dead key is present;
WARN when an existing consumer config still contains `features.project_board`;
never FAIL. Its next action would be: "Remove features.project_board; this
setting has never changed what shipshape installs." Existing configs remain
untouched until their owner accepts a config change.

**Classification — `do-now`.** Removing an unimplemented default and warning
about a no-op value changes no settled behavior and needs no ADR.

**Constraint check.** The doctor change remains stdlib/JSON under ADR 0002;
new defaults affect only future rendering and existing configs are never
clobbered under ADR 0003; the agent lane is unchanged under ADR 0004; and the
warning says exactly what the setting did and the one safe next action.

### 14. Consumers receive no agent-sandboxing guidance

**Gap.** The research assumes a generator can be prompt-injected and says it
should run sandboxed by default. Shipshape tells agents to use CI and avoid
secrets, but does not tell consumers to restrict the agent's filesystem,
credentials, or mutation scope.

**Evidence.** Tier 2 evidence supports hardening CI against automation and
sandboxing agent execution on the assumption that generated work will
eventually attempt something it should not. This supports defense-in-depth
guidance; it does not prove that one host's sandbox is sufficient.

**Current state.** [`templates/security/security-explainer.md.tmpl`](../../templates/security/security-explainer.md.tmpl)
explains four guardrails but no agent isolation. The thin adapters in
`templates/adapters/*.tmpl` point to the harness and forbid weakening security,
but specify no host setting or access boundary.

**Proposed change, concretely.** Add a short "When an AI tool works here"
section to `templates/security/security-explainer.md.tmpl`: choose the tool's
restricted workspace mode; grant the repository, not unrelated folders;
withhold production credentials; approve extra access one request at a time;
and keep cloud changes in pull requests through CI. Do not name a vendor UI,
promise enforcement, or duplicate the section into thin adapters. This is an
existing ask-if-drifted `security` manifest entry, so no new entry, condition,
or feature is required.

**Classification — `do-now`.** Plain defense-in-depth guidance is compatible
with default-on security and the existing agent lane. It adds no unsupported
claim that the kit can enforce a sandbox.

**Constraint check.** This is documentation only under ADR 0002; the existing
token-only, ask-if-drifted template preserves ADR 0003; the guidance explicitly
keeps the ADR 0004 proposal/CI/human path; and it is written as short,
non-technical consequences and actions for non-engineers.

## Historical roadmap sketch

This is the 2026-08-13 planning snapshot, not a completion report. ADRs 0005–0009
later settled several items; ADR 0010 corrects the automation and control-path
assumptions. Prospective work below must still be verified independently.

### v0.3

1. Remove the dead `project_board` default and add the unused-setting WARN;
   this is low-risk cleanup that restores config honesty.
2. Add the `test retries` doctor warning; it cheaply protects the meaning of
   green before change volume grows.
3. Add consumer sandboxing guidance; it closes a clear documentation gap
   without pretending to enforce a host feature.
4. Write the agent-control-surface ADR, then extend the guard and reviewer
   together; Tier 1 attack evidence makes this the first behavioral decision.
5. Write the scheduled-health ADR, then distribute the self-contained doctor
   before adding its workflow; the executable must exist before the clock can
   call it.
6. Write the findings-first review ADR and update the skill plus both generated
   briefings as one contract; this improves use of human attention without yet
   changing merge authority.

### v0.4

1. Write the lightweight-intent ADR and pilot the four-field artifact; intent
   conformance becomes meaningful only after intent has a durable home.
2. Evaluate the weekly security-quality prototype against a fixed alert set,
   token setup, and cost budget; ship it only if the research-first gate closes.
3. Prototype verification-cost visibility and choose a decision-relevant,
   provider-neutral measure before adding any budget language.
4. Pilot the corrected ordinary-docs-only lane from ADR 0010 behind explicit
   trusted-base configuration and exact source-bound enforcement. Dependencies
   remain human-reviewed.

### Later

1. Complete the assertion-free and mutation-testing study before choosing any
   test-quality gate; cross-language feasibility and CI cost are unresolved.
2. Revisit provenance labeling only after a label demonstrates audit value;
   never treat provenance as proof of intent or safety.
3. Revisit platform-specific progressive delivery only when controlled
   deployment evidence and a first supported target exist; it remains additive
   to pre-merge review.

## ADR questions from the 2026-08-13 snapshot

- **Scheduled stewardship for consumer repositories** — Should shipshape
  render a self-contained doctor and run it weekly, and when may it write or
  update an issue?
- **Findings-first semantic review** — What constitutes a verified finding,
  how is missing intent represented, and which existing verdict guarantees
  remain invariant?
- **Agent and editor control files as security-sensitive paths** — Which paths
  and executable settings WARN or FAIL, and how are false positives reviewed
  without weakening the guard?
- **Tiered review authority behind green gates** — superseded in implementation
  by ADR 0010's ordinary-docs-only, immediate-merge contract with no automatic
  break-glass.
- **Lightweight durable change intent** — Which changes need an in-repo intent
  artifact, what is the trivial-change escape hatch, and when may intent change?

## Closing

Three questions remain material. Test-quality work needs recall and mutation
evidence before it becomes more than an assertion-absence advisory. The
ordinary-docs automatic lane needs local refusal and false-eligibility evidence
under ADR 0010, not a borrowed override threshold. Controlled deployment
evidence would decide whether progressive delivery can become more than a
platform-specific sketch, though never by treating it as a review replacement.

Two more findings would change scope rather than order. A measurable proxy for
comprehension debt could add a stewardship sensor not present in this register,
and an eval of the kit-local security-quality agent would answer whether
shipshape should ship any inferential sensor at all. On 2026-09-09 the
[DORA publications index](https://dora.dev/research/publications/) still
presented the 2025 state report and companion guides; that observation, rather
than a categorical claim that no 2026 publication exists, may change on a later
check. Missing primary evidence could adjust confidence, but
perception data, panic literature, provenance attestations, and contested
junior/senior claims would still not justify kit behavior on their own.
