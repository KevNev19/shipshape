# Integrating the mattpocock-skills processes: worth the effort?

- Status: Research results (2026-08-14). Accepted 2026-08-22: all four
  proposals (three binds and the research fence) applied to
  [docs/agents/harness.md](../agents/harness.md).
- Purpose: per-skill decision on binding the mattpocock-skills plugin's
  processes into shipshape's pipeline. Changes no policy; recommended
  binds are proposals for [docs/agents/harness.md](../agents/harness.md)
  pending Kevin's acceptance. Design:
  [study design](../superpowers/specs/2026-08-14-mattpocock-skills-integration-study-design.md).

## Method

Two parallel read-only agents produced the inputs: an inventory of all
eleven skills from their installed `SKILL.md` files (plus twenty-two
additional skills the plugin ships that the study catalogued but does not
judge), and a stage-by-stage map of the pipeline as practiced, swept
against every orchestration run's journal and event streams for evidence
of these skills actually firing. Each skill receives exactly one verdict —
bind / redundant / conflicts / situational — for the kit-development
surface, and yes/no for the consumer surface, which defaults to no unless
the skill survives ADR 0001's inert-tooling rule. Every verdict cites a
skill-file fact or a run-history event traceable to the two agent inputs;
some rationales additionally reference repo facts (an ADR, a file layout)
verified directly against the repository — no verdict rests on one alone.

## The pipeline as it stands

| Stage | Bound today (harness) | Owner |
|---|---|---|
| Shape | superpowers `brainstorming` | Claude with Kevin |
| Plan | superpowers `writing-plans` → orchestrator task entries | Claude |
| Implement | codex-orchestrator only; superpowers `test-driven-development` governs content | Codex |
| Verify | superpowers `verification-before-completion`, `systematic-debugging` | Claude, binding |
| Review and close | code-review discipline feeds journal `verification` entries; orchestrator validate → run_closed → report | Claude |

Conflict rule: the orchestrator wins on who implements and on run records;
superpowers wins on how work is shaped, tested, and verified.

## Verdict table

| Skill | Kit-dev verdict | Consumer surface | Binding point (if bind) |
|---|---|---|---|
| code-review (two-axes) | **bind** | no | Implement: sanctioned pre-handoff self-review in Codex task prompts |
| writing-for-agents | **bind** | no | Cross-cutting: consulted when editing templates/, skills/, or agent-facing docs |
| codebase-design | **bind** | no | Shape: interface/seam vocabulary for engine and template design |
| tdd | redundant | no | — |
| diagnosing-bugs | redundant | no | — |
| research | **conflicts** | no | — (fence: never invited in Codex prompts) |
| grilling | situational | no | — (trial at next ADR acceptance) |
| domain-modeling | situational | no | — |
| prototype | situational | no | — |
| resolving-merge-conflicts | situational | no | — |
| wizard | situational | no | — |

## Per-skill rationale

**code-review — bind.** Eighteen uninvited self-invocations with two
traced instances of real defects caught pre-handoff (magic-number window;
fail-soft crash plus three safety edge cases). Its two-axes structure
(Standards vs Spec, never merged) occupies a different layer than ADR
0007's findings-first contract: this is the *implementer's* self-check
before handoff; ADR 0007 governs what the *reviewer* reports to the human.
Formalizing means task prompts acknowledge the chain rather than each
Codex agent rediscovering it. For symmetry with the redundancy test
applied elsewhere: superpowers ships `requesting-code-review` and
`receiving-code-review`, but neither is bound anywhere in the harness or
`CLAUDE.md`, so there is no equivalent to defer to. What would change
this verdict: evidence that the self-review pass materially lengthens
runs without catching defects.

**writing-for-agents — bind.** No run evidence (it fires on skill/agent-doc
authoring, which Codex tasks so far have not been), but the strongest
skill-file case in the set: shipshape's *product* is agent-consumed
documents — adapters, harness templates, skill files — and this is a
discipline for exactly that (context pointers, progressive disclosure,
completion criteria, no-op hunting). Nothing in superpowers covers it.
Binding point is cross-cutting: a sentence in the harness's Design rules
section, consulted whenever templates/, skills/, or the agent-facing docs
are edited. What would change this verdict: a trial period in which
consulting it demonstrably adds authoring overhead without improving the
docs agents actually follow.

**codebase-design — bind.** Eleven uninvited self-invocations during
engine work; no superpowers equivalent for its deep-module vocabulary
(depth, seams, adapters, the deletion test). Natural home is shape-stage
design discussions for scripts/ and template structure. What would change
this verdict: shape-stage sessions where the vocabulary is invoked
without changing any design decision.

**tdd — redundant.** The harness already binds superpowers'
`test-driven-development` to govern implementation content, and the local
file is near-identical in substance. The observed double-reading was
harmless reinforcement, but naming both in policy would invite
dual-vocabulary drift — the same concern that motivates ADR 0004's
mirror-by-reference pattern for consumer adapters, applied here by
analogy. The superpowers binding stands alone.

**diagnosing-bugs — redundant.** Superpowers' `systematic-debugging` is
already bound at verify. The evidence agrees the gap is theoretical: zero
reads ever, while two real debugging cycles (the CI false-positive) ran a
clean diagnose→reproduce→fix loop on prose discipline alone.

**research — conflicts.** The verdict rests on the skill's design, not on
the severity of the one observed firing. Its core instruction is to "spin
up a background agent" — so any invocation inside a Codex execution
sub-delegates by construction, and the one traced instance confirmed the
consequence: sandbox-internal delegation invisible to the orchestrator's
journal, which the pipeline map classified as neutral-to-mildly-clashing
("a small friction against the harness's claim that its journal is the
record of work"; the output still passed all four independent checks).
Mild in that instance, structural in kind — which is why the verdict is
conflicts rather than situational. The fence is narrow: Codex task
prompts must not invite it; Claude-side research already runs under
session patterns that do the accounting. What would change this verdict:
a revision of the skill that reports its delegation to the caller.

**grilling — situational.** No run evidence, and superpowers'
`brainstorming` covers shape-stage questioning. Its frontier/design-tree
method is genuinely different (adversarial, exhaustive, decision-scoped)
and the natural experiment is cheap: run it once before the next ADR
acceptance. If it surfaces assumptions the drafting process missed, it
earns a narrow pre-ADR bind; until then it stays on demand.

**domain-modeling — situational.** The glossary discipline (challenge
conflicting terms, sharpen inline, offer ADRs sparingly) is sound. But
its `CONTEXT.md` file convention collides with the kit's established
homes (`docs/sdlc/design.md`, `docs/sdlc/glossary.md`), so it is a
discipline to borrow, not a file layout to adopt.

**prototype — situational.** Useful shape-stage tool, but it assumes
throwaway branches off main — colliding with the trunk-only rule, whose
worktree carve-out is scoped to orchestrator-managed isolation only. Usable
with adaptation (scratch directories) when a design question warrants it.

**resolving-merge-conflicts — situational.** Sound five-step discipline;
a trunk-based single-committer repo simply rarely needs it.

**wizard — situational.** Made for human-only steps the agent cannot do —
the exact shape of `tests/e2e.sh`'s manual walkthrough half and, someday,
consumer onboarding. A tool to reach for, not a pipeline stage.

**Consumer surface — no, across all eleven.** ADR 0001 requires that
everything shipshape writes into consumer repos be inert standard tooling
that survives plugin removal; referencing any third-party plugin's process
in shipped artifacts breaks that. The plugin's unpackaged issue-tracker
suite (`to-spec`, `to-tickets`, `triage`, `wayfinder`) is noted as future
research relevant to the intent-capture story around ADR 0009 — a separate
decision with its own evidence bar.

## Evidence: where his skills already fired

The study set out to ask whether these processes *should* be tied into
the pipeline; the sweep answered a different question — they already are.
Codex implementation agents have been reading Kevin's personal skills
library at `~/.agents/skills/` (verified present; the staging source of
the packaged plugin) on their own initiative in nearly every
implementation execution, in a consistent chain: "implement → tdd →
review" at task start, superpowers' `verification-before-completion`
before handoff. No prompt invited this; no config names that directory.
The real decision is therefore not "integrate or ignore" but formalize,
fence, or leave tacit — per skill. The instances, each classified:

- **Helped** — dead-flag/doctor-checks run: the self-invoked two-axes
  `review` pass found an unexplained magic-number window in a new loop
  scan, fixed before handoff.
- **Helped** — ADR 0008 run: the same self-invoked `review` pass found a
  fail-soft bug (a wrong-shaped JSON API response could crash the doctor
  instead of WARNing) plus three safety edge cases, all fixed before
  Claude's independent verification ever saw the work.
- **Helped (aggregate)** — the personal-library read counts across runs:
  review ×18, implement ×18, codebase-design ×11, tdd ×10,
  edit-article ×2 — self-directed in every case, with no observed clash:
  the chain runs inside the implementer's turn, and Claude's independent
  verification still executed every time.
- **Clashed (mildly)** — the single literal plugin-cache hit: the
  `research` skill self-invoked inside a Codex execution, whose
  background-delegation instruction produced sandbox-internal
  sub-delegation invisible to the run journal (classified
  neutral-to-mildly-clashing by the sweep; the output still passed all
  four independent checks).
- **Neutral** — `diagnosing-bugs` was never read (zero hits ever), while
  two real debugging cycles around the CI false-positive ran a clean
  diagnose→reproduce→fix loop on prose discipline alone — the process it
  covers happened without it.

Confirmed distinctions and side-catches, for the record: a separate
session's run used `codex-review-*` agents for the harness's own
plan-review phase, unrelated to the mattpocock review skill (zero skill
reads in those executions); the oldest run predates the Codex profile
mandate (historical compliance gap, not a live violation); and the fact
that Codex agents read a personal skills library uninvited is itself a
control-surface observation adjacent to ADR 0005's theme — the library is
outside the repo, so the guard does not see it.

## Draft harness amendment (for the binds only)

Three sentences, at three points in `docs/agents/harness.md`:

1. *Implement stage:* "Codex task prompts sanction the implementer's
   pre-handoff two-axes self-review (the local `review` skill it already
   reaches for)."
2. *Shape stage:* "Interface and seam design for the engine consults the
   `codebase-design` vocabulary (deep modules, the deletion test)."
3. *Design rules section:* "Edits to templates/, skills/, or agent-facing
   docs consult `writing-for-agents` before writing."

Each sentence is severable — accepting one does not imply another. The
`research` fence is deliberately not here: it is the output of a
conflicts verdict, not a bind, and stands in that skill's rationale as
its own fourth, separately decidable proposal.

## What this study does not decide

Whether the issue-tracker suite has a place in shipshape's future intent
story (ADR 0009 territory); whether grilling earns its pre-ADR bind (one
trial decides); anything about the consumer surface beyond the ADR 0001
default; and the governance question of whether uninvited personal-library
reads by implementation agents should themselves be fenced — that is a
control-surface decision for Kevin, recorded here as an observation only.
