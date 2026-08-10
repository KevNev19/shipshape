# shipshape — Instructions for AI Agents

This repo's policy lives in `docs/agents/harness.md`. Read it first; it is
the source of truth for design rules, quality gates, and session close.
Keep Claude-specific setup here small — substantive policy belongs in the
harness doc and must be mirrored only by reference, not rewritten
differently.

Implementation work goes through the codex-orchestrator plugin by default —
see "Default workflow: orchestrated implementation" in the harness doc. Every
Codex execution uses `--profile shipshape` (gpt-5.6-sol at xhigh reasoning).

Quick facts:

- This IS the shipshape kit: plugin manifests in `.claude-plugin/`, skills
  in `skills/`, engine in `scripts/`, templates in `templates/`.
- Tests: `python3 -m pytest tests/ -q` (frozen fixtures are ground truth).
- Decisions: `docs/adr/` (supersede, don't edit).
