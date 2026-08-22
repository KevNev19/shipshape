# How We Work on shipshape

Model-neutral source of truth for every coding agent working on the
shipshape kit itself. Tool-specific files (`CLAUDE.md`) add runtime wiring
only and must mirror this file by reference, not rewrite it differently.

## First steps

- Read `docs/adr/` before changing any settled behaviour; supersede, don't
  edit (see `docs/adr/adr-guide.md`).
- Check `git status --short` before editing so your changes stay
  distinguishable from existing work.

## Design rules

- Kit scripts: Python 3 stdlib only, JSON-only stdout (ADR 0002).
- Templates: `{{TOKEN}}` substitution only, variants over logic, every
  artifact self-documenting with a managed-by header (ADR 0003).
- Skills sequence scripts and follow the voice contract in
  `skills/shipshape-init/references/voice.md`; they contain no logic.
- The never-clobber drift contract is inviolable: nothing overwrites a
  user-edited file without an explicit per-file force.
- Edits to templates/, skills/, or agent-facing docs consult
  `writing-for-agents` before writing (accepted from
  `docs/research/0004-mattpocock-skills-integration.md`).

## Default workflow: orchestrated implementation (the only way)

All implementation work on this repo runs through one layered pipeline
combining the superpowers plugin (discipline for the driving session) and
the codex-orchestrator plugin (delegated implementation). The driving
Claude session shapes, plans, and independently verifies; Codex agents
implement. This is not a preference — it is the standing working mode for
this project.

The pipeline, phase by phase:

1. **Shape (superpowers).** Any creative work — features, components,
   behavior changes — starts with the `brainstorming` skill: intent,
   requirements, and design explored with Kevin before anything else.
   Interface and seam design for the engine consults the
   `codebase-design` vocabulary (deep modules, the deletion test).
2. **Plan (superpowers → orchestrator).** `writing-plans` produces the
   plan; its steps map one-to-one into orchestrator `task` entries with
   goals, acceptance criteria, and owned files. Use the orchestrator's
   Codex plan-review step when a second opinion materially reduces risk.
3. **Implement (codex-orchestrator only).** Superpowers'
   `subagent-driven-development` and `executing-plans` are subordinated
   here: the "subagents" that implement are ALWAYS Codex agents launched
   via `/codex-orchestrator:orchestrate` — never Claude subagents editing
   files. The `test-driven-development` skill governs execution *content*:
   task prompts demand red-green-refactor, and acceptance criteria include
   the failing-test-first evidence. Codex task prompts sanction the
   implementer's pre-handoff two-axes self-review (the local `review`
   skill it already reaches for), and must not invite the `research`
   skill's background delegation, which bypasses the run journal (both
   accepted from `docs/research/0004-mattpocock-skills-integration.md`).
4. **Verify (superpowers, binding on Claude).**
   `verification-before-completion` is the verifier's law: evidence before
   assertions, gates actually run, never accept an implementing agent's
   claim of success. `systematic-debugging` drives any failed-execution
   diagnosis before a retry cycle.
5. **Review and close (both).** Code-review discipline feeds the journal's
   `verification` entries; the orchestrator's close sequence
   `validate → run_closed → report.md` remains canonical and final.

- Front doors: `/codex-orchestrator:workflow` owns a full run end to end;
  `/codex-orchestrator:orchestrate` runs each focused agent cycle inside it;
  `/codex-orchestrator:report` writes the final report after `run_closed`.
- **Every Codex execution launches with `--profile shipshape`** (defined in
  `~/.codex/shipshape.config.toml`: model `gpt-5.6-sol`,
  `model_reasoning_effort = "xhigh"`). No unprofiled or lower-effort
  executions.
- Follow the plugin's orchestration contract exactly: run initialization
  with the local git exclude of `/.codex-orchestrator/`; an append-only
  `journal.jsonl` (never rewrite history); `task` entries with goals,
  acceptance criteria, and owned files; `execution` records carrying the
  exact prompt, events, and handoff; `verification` entries for material
  checks; and the canonical close sequence `validate → run_closed →
  report.md`.
- Delegation never waives a gate: every delegated result runs the Build and
  test gates below before acceptance, verified by Claude, not by the
  implementing agent's word.
- Exceptions: none by default. A direct (non-orchestrated) edit happens only
  when Kevin explicitly directs it for that specific task. Analysis-only or
  conversational work that changes no files needs no run.
- Plugin conflict rules: where superpowers and the orchestrator disagree,
  the orchestrator wins on WHO implements (Codex agents, profiled) and on
  run records (its journal is the record of work, not a parallel one);
  superpowers wins on HOW work is shaped, tested, and verified.
  `using-git-worktrees` applies only when the orchestrator's compute
  reference calls for isolated worktrees; `finishing-a-development-branch`
  applies only when work happens on a branch (this repo is trunk-based).

## Worktree carve-out (explicit exception to the global no-worktrees rule)

Kevin's global rules forbid branches and worktrees; for this project ONLY,
orchestrator-managed isolation is the sanctioned exception, under these
bounds:

- Worktrees exist only when the orchestrator's compute rules require them
  (overlapping task `files` or shared resources — disjoint tasks stay in
  the main tree), created exactly as the contract prescribes
  (`git worktree add ../shipshape-codex-impl-NN -b codex-impl-NN`).
- They are machine-managed and MUST NOT outlive their run: after
  integration and target-side acceptance checks, the worktree is removed
  and its `codex-impl-NN` branch deleted in the same task cycle.
- Session close adds a hygiene check: `git worktree list` shows only the
  main tree, and `git branch --list 'codex-impl-*'` is empty. A stray
  worktree or branch found at close is cleaned up (after confirming its
  run is terminal) before the session reports done.
- Humans never work in these worktrees; Kevin's own work stays on `main`.

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

Every commit tells its story: subject, why, what, and who. Enforced by
`scripts/check_commit_msg.sh` at commit-msg stage (merges/reverts exempt).

- Subject: conventional type (`feat:`/`fix:`/`docs:`/`chore:`/`test:`),
  imperative mood, aim for 50 characters, hard cap 72. Blank line after.
- Body: a `Why:` line (the problem or reason) and a `What:` line (the
  change itself — prose or bullets), wrapped at 72.
- Attribution: a `Co-authored-by:` trailer for EVERY AI agent whose work is
  in the commit, using these canonical identities:
  - `Co-authored-by: Claude <noreply@anthropic.com>`
  - `Co-authored-by: Codex (gpt-5.6-sol) <noreply@openai.com>`
  - `Co-authored-by: Copilot <175728472+Copilot@users.noreply.github.com>`
- **Explicit override (Kevin, 2026-08-11):** the global rule forbidding AI
  attribution in commits does NOT apply to this project. Shipshape is an
  AI-native SDLC project; honest agent attribution is part of its git
  history by design. This override is scoped to this repository only.

## Session close

- Run the gates above before reporting work done; report results honestly.
- Trunk-based: work lands on `main` in small, deployable, conventional
  commits. Never push without being asked.
