# mattpocock-skills Integration Study Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce `docs/research/0004-mattpocock-skills-integration.md` — a per-skill, evidence-cited verdict on whether binding the mattpocock-skills processes into shipshape is worth the effort, scored separately for kit development and consumer surfaces.

**Architecture:** Two parallel read-only research agents produce the raw inputs (installed-skill inventory; pipeline-as-practiced map with run-journal evidence). The orchestrating Claude session cross-maps them into the verdict document. No code changes; no policy changes; docs-only commit.

**Tech Stack:** Claude research agents (Explore type), the installed mattpocock-skills plugin cache, this repo's `.codex-orchestrator/runs/` journals, git.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-14-mattpocock-skills-integration-study-design.md` — its Method and Output sections are binding.
- Verdict vocabulary is exactly: `bind` / `redundant` / `conflicts` / `situational` (kit surface) and `yes` / `no` (consumer surface, defaulting to `no` unless the skill survives ADR 0001's inert-tooling rule).
- Every verdict cites a skill-file fact or a run-history event. No unsupported claims.
- The study changes no policy: no edits to `docs/agents/harness.md`, `CLAUDE.md`, any ADR, any template, or any skill.
- Execution starts only after the in-flight ADR 0008 verification (run-20260814-04) has been completed and committed — the working tree must be clean before Task 1.
- Commit messages follow the kit convention: subject ≤72 chars, blank line, `Why:` and `What:` body lines (enforced by `scripts/check_commit_msg.sh`).

---

### Task 1: Launch the two research agents in parallel

**Files:**
- Create: none (agents are read-only; final messages are their deliverables)

**Interfaces:**
- Produces: two agent reports in the session — `skills-inventory` (per-skill: purpose, process steps, triggers, outputs, natural pipeline stage) and `pipeline-map` (stage-by-stage bindings + every uninvited mattpocock-skill firing found in run history with helped/clashed/neutral classification). Task 2 consumes both verbatim.

- [ ] **Step 1: Confirm the precondition gate**

Run: `git status --short -- ':!.codex-orchestrator'`
Expected: empty output (ADR 0008 work committed). If not empty, STOP — finish the ADR 0008 verification first.

- [ ] **Step 2: Launch agent `skills-inventory` (Explore type, parallel with Step 3)**

Prompt (verbatim):

> Inventory the mattpocock-skills plugin installed at
> `~/.claude/plugins/cache/` (find the exact directory with
> `ls ~/.claude/plugins/cache/ | grep -i pocock` and locate its skills/
> subdirectories). Read every SKILL.md fully — expected skills:
> diagnosing-bugs, tdd, prototype, research, domain-modeling,
> codebase-design, code-review, resolving-merge-conflicts, wizard,
> grilling, writing-for-agents (report any additions/absences). For EACH
> skill return: (1) purpose in one sentence; (2) its process steps
> compressed to 3-6 bullets; (3) trigger conditions (when it says it
> should fire); (4) outputs/artifacts it produces (files, reports,
> decisions); (5) which pipeline stage it naturally belongs to: shape /
> plan / implement / verify / close / cross-cutting; (6) any explicit
> assumptions it makes about workflow (branches, worktrees, commit
> practices, who implements). Quote sparingly but exactly where wording
> matters. Do NOT write any files — your final message is the deliverable.

- [ ] **Step 3: Launch agent `pipeline-map` (Explore type, parallel with Step 2)**

Prompt (verbatim):

> Map shipshape's development pipeline as practiced, at
> /Users/yodabender/Projects/shipshape. (1) From `docs/agents/harness.md`
> (read fully): list each pipeline stage (shape, plan, implement, verify,
> close) with the exact skills/plugins the harness binds at each, plus the
> conflict rules and the worktree carve-out. (2) From `CLAUDE.md`: the
> Codex profile mandate. (3) Evidence sweep: for every run under
> `.codex-orchestrator/runs/` read `journal.jsonl` and grep the
> `codex-*/execution-*/events.jsonl` files for `mattpocock` — for each hit
> identify WHICH skill fired, in whose context (Codex agent vs Claude),
> whether it was invited by the prompt or fired uninvited, and classify
> its effect: helped / clashed / neutral (with one line of evidence, e.g.
> the two-axes code-review skill appearing during the editorial run's
> self-review). Also note any place a run followed a process a mattpocock
> skill covers without the skill firing (e.g. debugging without
> diagnosing-bugs). Do NOT write any files — your final message is the
> deliverable.

- [ ] **Step 4: Verify both reports arrived complete**

Check: `skills-inventory` covers all 11 skills with all 6 fields; `pipeline-map` covers all 5 stages plus the evidence sweep with at least the two known leak instances. If either is partial, message that agent for the missing pieces before proceeding.

### Task 2: Synthesize the verdict document

**Files:**
- Create: `docs/research/0004-mattpocock-skills-integration.md`

**Interfaces:**
- Consumes: both Task 1 reports.
- Produces: the committed study document; its verdict table is what Kevin accepts or rejects.

- [ ] **Step 1: Write the document with this exact skeleton**

```markdown
# Integrating the mattpocock-skills processes: worth the effort?

- Status: Research results (2026-08-14)
- Purpose: per-skill decision on binding the mattpocock-skills plugin's
  processes into shipshape's pipeline. Changes no policy; recommended
  binds are proposals for docs/agents/harness.md pending Kevin's
  acceptance. Design: [study design](../superpowers/specs/2026-08-14-mattpocock-skills-integration-study-design.md).

## Method
(two-agent inputs; cross-map; verdict vocabulary; citation rule;
two surfaces — compress the spec's Method section to one paragraph)

## The pipeline as it stands
(stage table from pipeline-map: stage → bound skills → owner)

## Verdict table
| Skill | Kit-dev verdict | Consumer surface | Binding point (if bind) |
(11 rows; consumer column defaults to no)

## Per-skill rationale
(one short section per skill: verdict, the citation — skill-file fact or
run event — and for contested calls, "what would change this verdict")

## Evidence: where his skills already fired
(the leak instances from pipeline-map, classified helped/clashed/neutral)

## Draft harness amendment (for the binds only)
(the exact sentences that would change in docs/agents/harness.md, per
stage — written as a PROPOSAL, clearly marked not-yet-policy)

## What this study does not decide
(consumer exposure mechanics; trial measurements; anything ADR-worthy)
```

- [ ] **Step 2: Self-check the hard rules**

Check each verdict row: has a citation in its rationale section; consumer column is `no` unless an explicit ADR 0001 argument appears; every `bind` has a named binding point; vocabulary matches the Global Constraints exactly. Fix inline.

- [ ] **Step 3: Commit**

```bash
git add docs/research/0004-mattpocock-skills-integration.md
git commit -m "docs: study mattpocock-skills integration

Why: the skills already fire uninvited inside orchestration runs while
having no de-jure place in the pipeline; binding, fencing, or ignoring
them needed per-skill evidence rather than ad-hoc adoption.

What: add the gap-fill and conflict study - per-skill verdicts across
kit-development and consumer surfaces with skill-file and run-history
citations, the leaked-usage evidence, and a draft harness amendment
proposal for the binds."
```

### Task 3: Verify, push, and confirm CI

**Files:**
- Modify: none

**Interfaces:**
- Consumes: the Task 2 commit.
- Produces: green CI on the pushed study; the board update for Kevin.

- [ ] **Step 1: Run the repo gates (docs-only change, gates must stay green)**

Run: `python3 -m pytest tests/ -q` → Expected: `112 passed` (or current count) — unchanged.
Run: `ruff check . && ruff format --check .` → Expected: all clean.

- [ ] **Step 2: Push**

```bash
git push origin main
```

- [ ] **Step 3: Confirm CI green**

Run (background): `until [ "$(gh run list --branch main --limit 3 --json status --jq '[.[] | select(.status != "completed")] | length')" = "0" ]; do sleep 20; done; gh run list --branch main --limit 3`
Expected: CI, Secret scan, CodeQL all `success`.

- [ ] **Step 4: Report to Kevin**

Lead with the verdict table summary (how many bind/redundant/conflicts/situational), name the proposed binds and their binding points, state that the harness amendment is a proposal awaiting his acceptance, and note the consumer-surface outcome.

## Self-review record

- Spec coverage: Question → Tasks 1–2; Inputs → Task 1 Steps 2–3 (verbatim prompts); Method/hard rules → Task 2 Steps 1–2 and Global Constraints; Output → Task 2 skeleton; After → Task 3 Step 4. No gaps.
- Placeholder scan: agent prompts and doc skeleton are verbatim; commit message written out; no TBDs.
- Consistency: verdict vocabulary identical in Global Constraints, Task 2 skeleton, and Task 3 report step; agent names `skills-inventory`/`pipeline-map` used consistently.
