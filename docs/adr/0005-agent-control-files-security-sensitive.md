# 0005 — Treat agent and editor control files as security-sensitive paths

Date: 2026-08-13

## Status

Proposed

## Decision

The secret guard and the review surfaces treat files that can steer an AI
agent or launch editor tasks as a distinct, security-sensitive class of
change. The paths in scope are `.claude/**`, `.vscode/**`, `.github/agents/**`,
`.github/copilot-instructions.md`, `AGENTS.md`, `CLAUDE.md`, and `.sdlc/hooks/**`.

Concretely:

1. `templates/hooks/secret-guard.sh.tmpl` gains a third, path-sensitive layer.
   Any change under the paths above prints a WARN naming the file and asking
   the committer to confirm they meant to change how automated tools behave.
   High-confidence additions of executable settings in JSON control files —
   task definitions, terminal or hook commands, encoded command strings —
   FAIL. Markdown instruction files are surfaced, never blocked merely for
   containing commands.
2. `.github/workflows/secret-scan.yml` runs the same layer over `base..HEAD`,
   so cloud-agent changes get identical treatment (per
   [ADR 0004](0004-github-agents-support.md)).
3. The review rubric in `skills/shipshape-review/references/review-rubric.md`
   and both generated GitHub review briefings report every control-file
   change as a security finding with its purpose and consequence.
4. `scripts/doctor.py` gains an `agent control-file coverage` check: PASS
   when guard layer and reviewer rule are present, WARN when only the
   deterministic layer is active, FAIL when `secret_guard` is enabled
   without the path-sensitive layer.

## Context

The August 2026 keyv npm compromise shipped malware carrying valid
provenance attestations, with payloads hidden in `.claude/` and `.vscode/`
files that dependency scanners never read. The research conclusion is
narrow and Tier 1: provenance answers "which pipeline built this," never
"should this change exist," and agent/editor configuration is an unscanned
attack surface. Today shipshape's guard checks credential-like filenames
and secret patterns only; no shipped control has path-sensitive rules for
files that change what a trusted tool executes. Full analysis: gap 5 of
[0002 — shipshape vs the AI-native SDLC](../research/0002-shipshape-vs-ai-native-sdlc.md).

## Consequences

- Every guardrail stays default-on, consistent with the kit's security
  posture; disabling the layer goes through the customize skill's
  consequence gate.
- False positives are the main cost: teams that legitimately iterate on
  agent config will see WARNs on most such commits. The WARN text must make
  confirming cheap (one re-run with the existing `--no-verify` escape hatch
  documented) and the FAIL patterns must stay high-confidence and short.
  If FAIL patterns prove noisy in practice, they are narrowed, never
  silently bypassed.
- The guard remains a POSIX shell script with no new dependencies
  ([ADR 0002](0002-python-stdlib-scripts.md)); template changes are token-only
  and ask-if-drifted ([ADR 0003](0003-token-substitution-templates.md)).
- Rejection criteria: if a pilot shows the WARN layer fires on more than
  roughly half of ordinary commits in agent-using repos, the path list is
  too broad and the decision should be reworked before shipping.
