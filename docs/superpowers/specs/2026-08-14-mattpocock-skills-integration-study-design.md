# Design: mattpocock-skills integration study

Date: 2026-08-14
Status: Approved design for a research study. The study changes no policy;
its output is a decision document.

## Question

Is tying the mattpocock-skills plugin's processes into shipshape — as bound
process steps, not copied content — worth the effort? Decided per skill,
with evidence, across two separately scored surfaces: the kit's own
development pipeline (`docs/agents/harness.md`) and shipshape's consumer
artifacts (bound by ADR 0001's inert-tooling rule).

## Inputs (two parallel agents)

1. **Skills inventory agent** — reads all 11 installed `SKILL.md` files
   from the mattpocock-skills plugin cache and returns, per skill: what it
   does, process steps, trigger conditions, outputs/artifacts, and the
   pipeline stage it naturally belongs to (shape / plan / implement /
   verify / close / cross-cutting). Ground truth is the installed skill
   files, not external descriptions.
2. **Pipeline-as-practiced agent** — maps the current harness pipeline
   stage-by-stage: which superpowers skills are bound where, the
   orchestrator's who-implements rule, and the documented conflict rules.
   Sweeps this session's eight orchestration run journals and Codex event
   streams for every place a mattpocock skill already fired uninvited
   (at least two known instances), recording whether it helped, clashed,
   or was neutral.

## Method

Cross-map inventory against pipeline. Each skill receives exactly one
verdict:

- **bind** — fills a real stage gap; comes with a named binding point
  (which harness sentence changes, at which stage);
- **redundant** — a superpowers equivalent is already bound; naming both
  would create the dual-vocabulary drift ADR 0004's mirror-by-reference
  rule exists to prevent;
- **conflicts** — contradicts who-implements, the verification law, or
  trunk-only rules;
- **situational** — useful on demand, wrong as a bound step.

Hard rules: every verdict cites a skill-file fact or a run-history event —
no unsupported claims; kit-development and consumer surfaces are scored
separately, and the consumer column defaults to **no** unless the skill
survives ADR 0001 (shipped artifacts must remain inert standard tooling
that survives plugin removal).

## Output

`docs/research/0004-mattpocock-skills-integration.md` containing: the
verdict table (both surfaces), per-skill rationale with citations, the
leaked-usage evidence from run history, a draft harness amendment sketch
for any binds, and a "what would change this verdict" note on each
contested call. Committed and pushed like research docs 0001–0003.

## After the study

Any recommended binds go to Kevin as a harness-amendment proposal
(policy — his call; a small ADR if settled workflow rules change).
Consumer exposure, if anything survives, becomes its own later decision.

## Out of scope

Copying or vendoring skill content; modifying the mattpocock plugin;
binding anything before Kevin accepts the study's recommendation; trial-
period measurements (explicitly deferred — the gap-fill + conflict map was
chosen as the decision standard).
