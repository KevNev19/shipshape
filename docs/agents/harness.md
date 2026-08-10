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

## Default workflow: orchestrated implementation (the only way)

All implementation work on this repo is delegated through the
codex-orchestrator plugin (enabled at project scope in
`.claude/settings.json`). The driving Claude session plans and independently
verifies; Codex agents implement. This is not a preference — it is the
standing working mode for this project.

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

## Build and test

```
python3 -m pytest tests/ -q
ruff check . && ruff format --check .
```

- Frozen fixtures (`tests/expected/*.json`) are ground truth — regenerate
  only when the correct answer genuinely changes, never to make a
  regression pass.
- Every bug fixed leaves a dated test in `tests/regressions.py`.

## Session close

- Run the gates above before reporting work done; report results honestly.
- Trunk-based: work lands on `main` in small, deployable, conventional
  commits. Never push without being asked.
