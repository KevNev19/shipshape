<!--
  What this is: a plain-language description of this project — what it is,
  what it's made of, and how to check it works. Generated once from a scan
  of the repository; after that it is yours.
  Safe to edit: yes, edit freely. Shipshape writes this file once and will
  not overwrite it.
  managed-by: shipshape v0.1.0
-->

# shipshape — Project Design

## What this project is

Shipshape is a plug-and-play SDLC kit delivered through Claude Code and Codex
plugin surfaces. Pointed at any git repository, it scans the project, asks a
few plain-language questions, and sets up a proper delivery process — CI,
security guardrails, reviews, and releases — for anyone, not just software
engineers. This repository is the kit itself, and these `docs/sdlc/` files were
produced by running the kit on its own repo.

## What it's made of

- Languages: python (kit scripts are stdlib-only by ADR 0002)
- Main language: python

## How to check it works

Run the tests with:

```
python3 -m pytest tests/ -q
```

The same tests run automatically on GitHub for every change
(`.github/workflows/ci.yml`), plus `tests/regressions.py` — one dated test
per historically fixed bug.

## Structure

- `.claude-plugin/` and `.codex-plugin/` — host-specific plugin manifests
- `skills/` — the user-facing commands (`/shipshape-init`, `/shipshape-doctor`),
  plus the host-aware orchestration adapter; each `SKILL.md` sequences scripts
  or an installed runtime and translates its result
- `scripts/` — the engine: `detect.py` (repo scan), `render.py` (template
  plan/apply with drift protection), `doctor.py` (health scorecard),
  `orchestrator.py` (read-only host routing), `gh_helpers.sh` (branch protection
  via the GitHub CLI)
- `templates/` — everything shipshape can write into a target repo, inventoried
  in `templates/manifest.json`
- `tests/` — frozen-fixture detection tests, render/drift tests, secret-guard
  and doctor tests, plus toy fixture repos under `tests/fixtures/`
- `docs/adr/` — decision records; `docs/agents/harness.md` — the kit's own
  development policy

## Decisions

Recorded as ADRs in `docs/adr/` — see `docs/adr/adr-guide.md` for the format.

The user-directed platform change of 2026-09-09 makes orchestration
host-aware: Claude hosts coordinate Codex workers through the existing
`codex-orchestrator`, while Codex hosts coordinate Claude workers through the
audited `codex-claude-orchestrator`. The selected host/model remains in charge;
Shipshape contains only the routing adapter, not another worker engine. ADR
0001 remains the historical record of the original Claude-only form factor.
