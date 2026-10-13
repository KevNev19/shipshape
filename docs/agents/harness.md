# How We Work on shipshape

Host-neutral source of truth for every coding agent working on the shipshape
kit itself. Tool-specific files (`AGENTS.md`, `CLAUDE.md`) add small entrypoint
pointers only and must not rewrite this policy differently.

## First steps

- Read `docs/adr/` before changing any settled behaviour; supersede, don't
  edit (see `docs/adr/adr-guide.md`).
- Check `git status --short` before editing so your changes stay
  distinguishable from existing work.

## Design rules

- Kit scripts: Python 3 stdlib only, JSON-only stdout (ADR 0002).
- Templates: `{{TOKEN}}` substitution only, variants over logic, every
  artifact self-documenting with a managed-by header (ADR 0003).
- User-facing setup skills sequence scripts and follow the voice contract in
  `skills/shipshape-init/references/voice.md`. Orchestration skills remain thin
  adapters over installed runtimes; they do not duplicate worker engines.
- The never-clobber drift contract is inviolable: nothing overwrites a
  user-edited file without an explicit per-file force.
- Edits to templates/, skills/, or agent-facing docs consult
  `writing-for-agents` before writing (accepted from
  `docs/research/0004-mattpocock-skills-integration.md`).

## Default workflow: host-selected orchestration

The user-directed platform mapping adopted on 2026-09-09 is based on the
actual tool host, not the coordinator's model:

- Claude host → `codex-orchestrator` → scoped Codex workers.
- Codex host → `codex-claude-orchestrator` → scoped Claude workers.

Use the model-invokable
[`shipshape-orchestrate`](../../skills/shipshape-orchestrate/SKILL.md) skill
for the deterministic route, installed entrypoint, provider-specific lifecycle,
and handoff rules. Preserve the user's selected coordinator and model. Small
routine work may stay in that coordinator when delegation has no net value.

The common flow is:

1. **Shape and plan.** Establish the goal, observable acceptance criteria,
   risks, exact owned paths, and verification path. Resolve only material
   ambiguity; already-authorized work needs no repeated approval.
2. **Route.** Pass the explicit host to `scripts/orchestrator.py`; never infer
   it from model names or inherited process variables. Record the selected
   host, provider, entrypoint, and reason.
3. **Execute.** Give one worker one bounded task. Behavior changes use a
   red-green-refactor loop. A worker never delegates back to the coordinator's
   provider or starts Shipshape recursively.
4. **Verify and close.** The coordinator inspects repository state and runs
   the material checks independently. A worker handoff is evidence to inspect,
   not authority to accept the task.

The selected upstream workflow owns lifecycle and records:

- On Claude hosts, `/codex-orchestrator:workflow` owns its append-only journal,
  exact prompts/events/handoffs, verification, validation, closure, and report.
  Every Codex CLI execution uses the existing `shipshape` profile; the profile
  retains its configured model and reasoning settings.
- On Codex hosts,
  `$codex-claude-orchestrator:claude-pty-agents` owns PTY admission, session
  identity, custody, handoff, process death, and retirement. The Codex host
  retains exact prompts, handoffs, and observed evidence in its normal task
  record without imposing the other plugin's journal.
- A run already in progress closes under the contract it started with. Never
  create a parallel journal for the same work.

All work stays in the canonical checkout on `main`: no branches or worktrees.
There is one writer at a time; serialize overlapping work, respect externally
owned paths, and preserve every unrelated dirty change. Changing providers
requires explicit authorization plus proven custody return from the current
runtime.

## Build and test

```
python3 -m pytest tests/ -q
ruff check . && ruff format --check .
```

- Frozen fixtures (`tests/expected/*.json`) are ground truth — regenerate
  only when the correct answer genuinely changes, never to make a
  regression pass.
- Every bug fixed leaves a dated test in `tests/regressions.py`.

## Commit messages

- Commit only when the user explicitly asks. Never push without being asked.
- Use a conventional type when appropriate, imperative mood, and a subject
  under 50 characters. Add a wrapped body when the change needs explanation.
- Write commit text as Kevin's work. Include no AI attribution or wording that
  discloses model or assistant involvement.

## Session close

- Run the gates above before reporting work done; report results honestly.
- Trunk-based: work lands on `main` in small, deployable, conventional
  commits. Never push without being asked.
