# shipshape

Set up a proper software delivery process in any git repository — in one
conversation, in plain English, for anyone. Shipshape is a Claude Code
plugin that scans your project, asks a handful of questions, and writes a
complete, working setup: automated tests, security guardrails, review and
release routines. Then it stays out of your way — everything it writes is
standard tooling that keeps working even if you remove the plugin.

## Install

Inside Claude Code, in any repository:

```
/plugin marketplace add KevNev19/shipshape
/plugin install shipshape@shipshape
```

Requirements: `git`, `python3` (preinstalled on macOS and most Linux), and
optionally the GitHub CLI (`gh`) for access management and branch protection.

## Quick start

```
/shipshape-init
```

Shipshape scans the repo, confirms what it found ("This looks like a Python
project that uses pytest — right?"), asks up to five plain-language
questions, shows you exactly what it will create, and writes it on your
go-ahead. Nothing is ever overwritten without asking — files you've edited
are detected and left alone.

## What you get

| | |
|---|---|
| **Guardrails** | A commit-time secret guard, CodeQL code scanning, Dependabot dependency watch, least-privilege CI — security is on by default and can be tuned, not skipped. |
| **Process** | A working agreement (`docs/sdlc/harness.md`), a generated project design doc, CI matched to your language, and — for teams — PR and issue templates with CODEOWNERS. |
| **Commands** | `/shipshape-doctor` (health check, security first), `/shipshape-review` (explains any change in plain language), `/shipshape-release` (guided, semver-correct releases), `/shipshape-access` (who can do what, via the GitHub CLI), `/shipshape-customize` (change anything off the defaults). |

Every generated file starts with a comment saying what it is, why you have
it, and whether it's safe to edit. A glossary (`docs/sdlc/glossary.md`)
explains every term the tooling uses.

## Customizing

One config file — `.sdlc/config.json` — drives everything: working style
(straight-to-main or pull-request), features on/off, commands, reviewers.
Change it with `/shipshape-customize` and shipshape regenerates only what's
affected. This repository was set up by running shipshape on itself; see
`docs/sdlc/`.

## Developing the kit

```
python3 -m pytest tests/ -q      # frozen-fixture, render, drift, guard, doctor tests
python3 tests/regressions.py     # one dated test per historically fixed bug
bash tests/e2e.sh                # end-to-end pipeline against a scratch repo
```

Design decisions live in `docs/adr/`. License: MIT.
