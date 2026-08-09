# 0002 — Kit scripts are Python 3 standard library only

Date: 2026-08-10

## Status

Accepted

## Context

Shipshape's scripts (`detect.py`, `render.py`, later `doctor.py`) run on
arbitrary consumer machines the moment the plugin is installed. Any
dependency — pip packages, Node, a compiled binary — becomes a setup step
that the target audience (non-engineers included) may not be able to
complete, and a support burden on every platform.

## Decision

All kit scripts are Python 3, standard library only. No pip, ever. Shell is
used only for git-hook shims where a shell is the native environment.
Scripts print exactly one JSON object on stdout and never prose; skills
branch on the JSON and do all the talking.

## Consequences

- The only runtime requirement is `python3` (present by default on macOS
  and most Linux; skills preflight it and explain installation when absent).
- Some conveniences (YAML parsing, rich templating) are off the table;
  templates are therefore plain-text token substitution (ADR 0003) and
  workflow files are written, not parsed.
- Windows support hinges on a python.org install; acceptable for v1.
